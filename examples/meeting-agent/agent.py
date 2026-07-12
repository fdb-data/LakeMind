import asyncio
import json
import logging
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from lakemind_client import LakeMindClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("meeting-agent")

_ASR_TAG_RE = re.compile(r"<\s*\|[^|]*\|\s*>")


def clean_asr_text(text: str) -> str:
    text = _ASR_TAG_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


TENANT_ID = os.environ.get("TENANT_ID", "retail")
S3_BUCKET = "lakemind-filesets"
CHUNK_DURATION = int(os.environ.get("CHUNK_DURATION", "10"))
SUMMARIZE_INTERVAL = int(os.environ.get("SUMMARIZE_INTERVAL", "6"))


class SSEBroker:
    def __init__(self):
        self._queues: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._queues.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self._queues:
            self._queues.remove(q)

    async def broadcast(self, event: str, data: dict):
        msg = f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        for q in self._queues:
            await q.put(msg)


class MeetingAgent:
    def __init__(self, client: LakeMindClient):
        self.client = client
        self.sse = SSEBroker()
        self.meetings: dict[str, dict] = {}

    def _s3_path(self, meeting_id: str, *parts: str) -> str:
        return f"s3://{S3_BUCKET}/{TENANT_ID}/meetings/{meeting_id}/" + "/".join(parts)

    async def start_meeting(self, title: str, participants: str) -> str:
        meeting_id = f"meeting-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        self.meetings[meeting_id] = {
            "title": title,
            "participants": participants,
            "chunks": 0,
            "summaries": 0,
            "extracts": 0,
            "transcript_buffer": [],
            "started_at": time.time(),
            "status": "recording",
        }
        logger.info("meeting started: %s (%s)", meeting_id, title)
        return meeting_id

    async def on_chunk(self, meeting_id: str, audio: bytes) -> dict:
        state = self.meetings.get(meeting_id)
        if not state:
            return {"text": "[meeting not found]", "segments": []}
        chunk_num = state["chunks"] + 1
        state["chunks"] = chunk_num

        wav_audio = LakeMindClient.convert_to_wav(audio)

        chunk_uri = self._s3_path(meeting_id, "audio", f"chunk-{chunk_num:03d}.wav")
        result_uri = self._s3_path(meeting_id, "results", f"asr-{chunk_num:03d}.json")
        await self.client.s3_put(chunk_uri, wav_audio)

        await self.sse.broadcast("status", {
            "status": state["status"],
            "chunks": chunk_num,
            "meeting_id": meeting_id,
        })

        if len(wav_audio) < 100:
            result = {"text": "[chunk too small]", "segments": []}
            logger.warning("chunk %d too small: %d bytes", chunk_num, len(wav_audio))
        else:
            try:
                job = await self.client.submit_job("asr", {
                    "chunk_uri": chunk_uri,
                    "result_uri": result_uri,
                })
                job_id = job["job_id"]
                logger.info("[SUBMIT] ASR chunk %d -> job %s", chunk_num, job_id)

                status = await self.client.poll_job(job_id, interval=1.0, timeout=120)
                ray_status = status.get("status", "")

                if ray_status in ("SUCCEEDED", "Completed", "completed"):
                    result_bytes = await self.client.s3_get(result_uri)
                    result = json.loads(result_bytes)
                    raw_text = result.get("text", "")
                    clean_text = clean_asr_text(raw_text)
                    result["text"] = clean_text
                    logger.info("[OK] ASR chunk %d: text_len=%d, text=%s",
                                chunk_num, len(clean_text),
                                clean_text[:60] if clean_text else "(empty)")
                else:
                    result = {"text": f"[ASR job {ray_status}]", "segments": []}
                    logger.error("[FAIL] ASR chunk %d: job status=%s", chunk_num, ray_status)
            except Exception as e:
                logger.error("[FAIL] ASR chunk %d: %s", chunk_num, e)
                result = {"text": f"[ASR error: {e}]", "segments": []}

        text = result.get("text", "")
        state["transcript_buffer"].append({"chunk": chunk_num, "text": text})

        elapsed = int(time.time() - state["started_at"])
        await self.sse.broadcast("transcript", {
            "text": text,
            "chunk": chunk_num,
            "timestamp": f"{elapsed // 60:02d}:{elapsed % 60:02d}",
        })

        if chunk_num % SUMMARIZE_INTERVAL == 0:
            asyncio.create_task(self._summarize(meeting_id))

        return result

    async def _summarize(self, meeting_id: str) -> dict | None:
        state = self.meetings[meeting_id]
        summary_num = state["summaries"] + 1
        state["summaries"] = summary_num

        transcript_text = " ".join(s["text"] for s in state["transcript_buffer"])

        transcript_uri = self._s3_path(meeting_id, "transcript.json")
        result_uri = self._s3_path(meeting_id, "results", f"summarize-{summary_num:03d}.json")
        await self.client.s3_put(transcript_uri, json.dumps({"text": transcript_text}).encode())

        try:
            job = await self.client.submit_job("summarize", {
                "transcript_uri": transcript_uri,
                "result_uri": result_uri,
                "meeting_title": state["title"],
            })
            job_id = job["job_id"]
            logger.info("[SUBMIT] Summarize #%d -> job %s", summary_num, job_id)

            status = await self.client.poll_job(job_id, interval=1.5, timeout=120)
            ray_status = status.get("status", "")

            if ray_status in ("SUCCEEDED", "Completed", "completed"):
                result_bytes = await self.client.s3_get(result_uri)
                result = json.loads(result_bytes)
                minutes = result.get("minutes", "")
                minutes_uri = result.get("minutes_uri", "")
                logger.info("[OK] Summarize #%d: text_len=%d", summary_num, len(minutes))
            else:
                logger.error("[FAIL] Summarize #%d: job status=%s", summary_num, ray_status)
                return None
        except Exception as e:
            logger.error("[FAIL] Summarize #%d: %s", summary_num, e)
            return None

        elapsed = int(time.time() - state["started_at"])
        await self.sse.broadcast("minutes", {
            "minutes": minutes,
            "updated_at": f"{elapsed // 60:02d}:{elapsed % 60:02d}",
        })

        if summary_num % 2 == 0:
            asyncio.create_task(self._extract(meeting_id, minutes, minutes_uri))

        return {"minutes": minutes, "minutes_uri": minutes_uri}

    async def _extract(self, meeting_id: str, minutes: str, minutes_uri: str) -> dict | None:
        state = self.meetings[meeting_id]
        extract_num = state["extracts"] + 1
        state["extracts"] = extract_num

        if not minutes_uri:
            minutes_uri = self._s3_path(meeting_id, "minutes.md")
            await self.client.s3_put(minutes_uri, minutes.encode())

        result_uri = self._s3_path(meeting_id, "results", f"extract-{extract_num:03d}.json")

        try:
            job = await self.client.submit_job("extract", {
                "minutes_uri": minutes_uri,
                "meeting_id": meeting_id,
                "meeting_title": state["title"],
                "result_uri": result_uri,
                "tenant_id": TENANT_ID,
            })
            job_id = job["job_id"]
            logger.info("[SUBMIT] Extract #%d -> job %s", extract_num, job_id)

            status = await self.client.poll_job(job_id, interval=1.5, timeout=120)
            ray_status = status.get("status", "")

            if ray_status in ("SUCCEEDED", "Completed", "completed"):
                result_bytes = await self.client.s3_get(result_uri)
                result = json.loads(result_bytes)
                concepts = result.get("concepts", [])
                logger.info("[OK] Extract #%d: %d concepts", extract_num, len(concepts))
            else:
                logger.error("[FAIL] Extract #%d: job status=%s", extract_num, ray_status)
                return None
        except Exception as e:
            logger.error("[FAIL] Extract #%d: %s", extract_num, e)
            return None

        try:
            check_query = concepts[0]["title"] if concepts else state["title"]
            check_result = await self.client.search_knowledge(
                query=check_query, kb_name="meetings", top_k=3,
            )
            hits = check_result.get("hits", [])
            logger.info("[OK] Retrieval self-check: query=%r, hits=%d",
                        check_query[:40], len(hits))
            for h in hits[:3]:
                logger.info("  hit: title=%r, distance=%s",
                            h.get("title", "")[:40], h.get("_distance"))
        except Exception as e:
            logger.warning("[FAIL] Retrieval self-check: %s", e)

        await self.sse.broadcast("knowledge", {"concepts": concepts})
        return {"concepts": concepts}

    async def stop_meeting(self, meeting_id: str) -> dict:
        state = self.meetings.get(meeting_id)
        if not state:
            return {"error": "meeting not found"}

        state["status"] = "stopped"

        if state["transcript_buffer"]:
            await self._summarize(meeting_id)

        elapsed = int(time.time() - state["started_at"])
        try:
            await self.client.add_memory(
                messages=[{
                    "role": "user",
                    "content": f"会议 '{state['title']}' 已结束，时长 {elapsed}s，共 {state['chunks']} 个音频片段。",
                }],
                metadata={"meeting_id": meeting_id, "title": state["title"]},
            )
            logger.info("[OK] Memory saved for meeting %s", meeting_id)
        except Exception as e:
            logger.warning("[FAIL] add_memory: %s", e)

        logger.info("[OK] Meeting stopped: %s, chunks=%d, summaries=%d, extracts=%d, duration=%ds",
                    meeting_id, state["chunks"], state["summaries"], state["extracts"], elapsed)

        return {
            "meeting_id": meeting_id,
            "title": state["title"],
            "duration": elapsed,
            "chunks": state["chunks"],
            "summaries": state["summaries"],
        }

    async def search(self, query: str, top_k: int = 5) -> dict:
        return await self.client.search_knowledge(query=query, kb_name="meetings", top_k=top_k)

    def list_meetings(self) -> list[dict]:
        result = []
        for mid, s in self.meetings.items():
            result.append({
                "meeting_id": mid,
                "title": s["title"],
                "participants": s["participants"],
                "chunks": s["chunks"],
                "status": s["status"],
                "started_at": s["started_at"],
            })
        return result


agent: MeetingAgent | None = None
client: LakeMindClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent, client
    client = LakeMindClient()
    agent = MeetingAgent(client)
    logger.info("MeetingAgent ready (skill_uri=%s, tenant=%s)", client.skill_uri, client.tenant_id)
    yield
    await client.close()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    with open(os.path.join(os.path.dirname(__file__), "static", "index.html"), encoding="utf-8") as f:
        return f.read()


@app.post("/api/start")
async def api_start(request: Request):
    body = await request.json()
    meeting_id = await agent.start_meeting(
        title=body.get("title", "未命名会议"),
        participants=body.get("participants", ""),
    )
    return {"meeting_id": meeting_id}


@app.post("/api/chunk")
async def api_chunk(request: Request):
    meeting_id = request.query_params.get("meeting_id", "")
    audio = await request.body()
    result = await agent.on_chunk(meeting_id, audio)
    return result


@app.post("/api/stop")
async def api_stop(request: Request):
    body = await request.json()
    meeting_id = body.get("meeting_id", "")
    result = await agent.stop_meeting(meeting_id)
    return result


@app.get("/api/stream")
async def api_stream(request: Request):
    queue = agent.sse.subscribe()

    async def event_stream():
        try:
            yield "event: connected\ndata: {}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=15)
                    yield msg
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            agent.sse.unsubscribe(queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/search")
async def api_search(query: str, top_k: int = 5):
    return await agent.search(query, top_k)


@app.get("/api/history")
async def api_history():
    return {"meetings": agent.list_meetings()}


def main():
    port = int(os.environ.get("PORT", "9100"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
