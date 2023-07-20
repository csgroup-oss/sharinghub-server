from fastapi import Request
from fastapi.exceptions import HTTPException
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRouter

from app.api.gitlab import GitlabClient, gitlab_api
from app.api.stac import build_collection, build_root_catalog, build_topic_catalog
from app.config import GITLAB_TOPICS

router = APIRouter(prefix="/{gitlab_base_uri}/{token}", tags=["stac"])


@router.get("/")
async def index(request: Request, gitlab_base_uri: str, token: str):
    return RedirectResponse(
        request.url_for("root_catalog", gitlab_base_uri=gitlab_base_uri, token=token)
    )


@router.get("/catalog.json")
async def root_catalog(request: Request, gitlab_base_uri: str, token: str):
    return build_root_catalog(
        topics=GITLAB_TOPICS,
        request=request,
        gitlab_base_uri=gitlab_base_uri,
        token=token,
    )


@router.get("/{topic_name:str}/catalog.json")
async def topic_catalog(
    request: Request, gitlab_base_uri: str, token: str, topic_name: str
):
    topic = GITLAB_TOPICS.get(topic_name)
    if not topic:
        raise HTTPException(
            status_code=404, detail=f"Topic '{topic_name}' not configured"
        )

    gitlab_client = GitlabClient(api_url=gitlab_api(gitlab_base_uri), token=token)
    projects = await gitlab_client.get_projects(topic_name)

    return build_topic_catalog(
        name=topic_name,
        fields=topic,
        projects=projects,
        request=request,
        gitlab_base_uri=gitlab_base_uri,
        token=token,
    )


@router.get("/{topic_name:str}/{project_path:path}/collection.json")
async def collection(
    request: Request,
    gitlab_base_uri: str,
    token: str,
    topic_name: str,
    project_path: str,
):
    gitlab_client = GitlabClient(api_url=gitlab_api(gitlab_base_uri), token=token)
    project = await gitlab_client.get_project(project_path)

    readme = await gitlab_client.get_readme(project_path)

    return build_collection(
        topic_name=topic_name,
        project_path=project_path,
        project=project,
        readme=readme,
        request=request,
        gitlab_base_uri=gitlab_base_uri,
        token=token,
    )
