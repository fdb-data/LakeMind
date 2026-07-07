from __future__ import annotations

import io
import zipfile

import yaml


def parse_ray_yaml(skill_zip: bytes, job_name: str) -> dict:
    with zipfile.ZipFile(io.BytesIO(skill_zip)) as zf:
        yaml_path = f"jobs/{job_name}/ray.yaml"
        names = zf.namelist()
        if yaml_path not in names:
            found = [n for n in names if n.startswith(f"jobs/{job_name}/")]
            if not found:
                raise ValueError(f"job '{job_name}' not found in skill package")
            raise ValueError(f"ray.yaml missing for job '{job_name}'")
        ray_yaml = yaml.safe_load(zf.read(yaml_path))
    return {
        "entrypoint": ray_yaml["entrypoint"],
        "dependencies": ray_yaml.get("dependencies", []),
        "resources": ray_yaml.get("resources", {}),
    }


def list_jobs(skill_zip: bytes) -> list[str]:
    job_names: set[str] = set()
    with zipfile.ZipFile(io.BytesIO(skill_zip)) as zf:
        for name in zf.namelist():
            if name.startswith("jobs/") and len(name) > 5:
                rest = name[5:]
                if "/" in rest:
                    job_names.add(rest.split("/")[0])
    return sorted(job_names)
