import asyncio
from typing import Any, TypedDict
from urllib import parse

from fastapi import HTTPException

from .utils import AiohttpClient, get_markdown_metadata


class GitlabProjectInfo(TypedDict):
    id: str
    description: str | None
    name: str
    name_with_namespace: str
    path: str
    path_with_namespace: str
    web_url: str


async def get_projects(
    gitlab_api_url: str, token: str, topic_name: str
) -> list[GitlabProjectInfo]:
    return await _request(
        gitlab_api_url, token, f"/projects?topic={topic_name}&simple=true"
    )


async def get_project_metadata(
    gitlab_api_url: str, token: str, project_path: str
) -> tuple[GitlabProjectInfo, dict[str, Any]]:
    project, readme = await asyncio.gather(
        *(
            get_project(gitlab_api_url, token, project_path),
            get_readme(gitlab_api_url, token, project_path),
        )
    )
    readme_metadata = get_markdown_metadata(readme)
    return project, readme_metadata


async def get_project(
    gitlab_api_url: str, token: str, project_path: str
) -> GitlabProjectInfo:
    return await _request(
        gitlab_api_url,
        token,
        f"/projects/{parse.quote(project_path, safe='')}",
    )


async def get_readme(gitlab_api_url: str, token: str, project_path: str) -> str:
    return await _request(
        gitlab_api_url,
        token,
        f"/projects/{parse.quote(project_path, safe='')}/repository/files/README.md/raw",
        media_type="text",
    )


async def _request(
    gitlab_api_url: str, token: str, endpoint: str, media_type="json"
) -> dict[str, Any] | list[Any] | str:
    async with AiohttpClient() as client:
        req = await client.get(
            f"{gitlab_api_url}{endpoint}", headers={"PRIVATE-TOKEN": token}
        )
        if req.ok:
            match media_type:
                case "text":
                    return await req.text()
                case "json" | _:
                    return await req.json()
        raise HTTPException(
            status_code=req.status,
            detail=f"{req.url}: {await req.text()}",
        )
