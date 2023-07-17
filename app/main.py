from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from .config import *
from .gitlab import get_project_metadata, get_projects, get_topic
from .utils import AiohttpClient, slugify


@asynccontextmanager
async def lifespan(app: FastAPI):
    aiohttp_client = AiohttpClient()
    aiohttp_client.connect()
    yield
    await aiohttp_client.close()


app = FastAPI(
    debug=DEBUG,
    title="STAC Dataset Proxy",
    description="STAC Dataset Proxy serves a STAC Catalog generated from Gitlab repositories.",
    version="0.1.0",
    root_path=API_PREFIX,
    docs_url="/docs",
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.get("/")
async def root_catalog(request: Request, token: str):
    topics_catalogs = [
        {
            "rel": "child",
            "href": str(
                request.url_for("catalog", topic_name=topic).include_query_params(
                    token=token
                )
            ),
        }
        for topic in GITLAB_TOPICS
    ]
    return {
        "stac_version": "1.0.0",
        "type": "Catalog",
        "id": "gitlab-stac-catalog",
        "title": "GitLab STAC Catalog",
        "description": f"Catalog generated from your [Gitlab]({GITLAB_URL}) repositories with STAC Dataset Proxy.",
        "links": [
            {
                "rel": "root",
                "href": str(request.url),
            },
            {
                "rel": "self",
                "href": str(request.url),
            },
            *topics_catalogs,
        ],
    }


@app.get("/{topic_name:str}")
async def catalog(request: Request, topic_name: str, token: str):
    topic = await get_topic(GITLAB_API_URL, token, topic_name)

    links = []
    if topic["id"]:
        projects = await get_projects(GITLAB_API_URL, token, topic_name)
        for project in projects:
            links.append(
                {
                    "rel": "child",
                    "href": str(
                        request.url_for(
                            "collection",
                            topic_name=topic_name,
                            project_path=project["path_with_namespace"],
                        ).include_query_params(token=token)
                    ),
                }
            )

    return {
        "stac_version": "1.0.0",
        "type": "Catalog",
        "id": f"gitlab-{slugify(topic['name'])}-stac-catalog",
        "title": topic["title"],
        "description": topic["description"]
        if topic["description"]
        else f"{topic['title']} catalog generated from your [Gitlab]({GITLAB_URL}) repositories with STAC Dataset Proxy.",
        "links": [
            {
                "rel": "root",
                "href": str(
                    request.url_for("root_catalog").include_query_params(token=token)
                ),
            },
            {
                "rel": "self",
                "href": str(request.url),
            },
            {
                "rel": "parent",
                "href": str(
                    request.url_for("root_catalog").include_query_params(token=token)
                ),
            },
            *links,
        ],
    }


@app.get("/{topic_name:str}/{project_path:path}")
async def collection(request: Request, topic_name: str, project_path: str, token: str):
    project, metadata = await get_project_metadata(GITLAB_API_URL, token, project_path)
    collection = {
        "stac_version": "1.0.0",
        "stac_extensions": ["collection-assets"],
        "type": "Collection",
        "id": f"gitlab-{slugify(project['name_with_namespace'])}",
        "title": project["name_with_namespace"],
        "description": project["description"]
        if project["description"]
        else f"{project['name']} collection generated from [Gitlab]({project['web_url']}) repository with STAC Dataset Proxy.",
    }
    collection |= metadata
    if "links" in collection:
        collection["links"].extend(
            [
                {
                    "rel": "root",
                    "href": str(
                        request.url_for("root_catalog").include_query_params(
                            token=token
                        )
                    ),
                },
                {
                    "rel": "self",
                    "href": str(request.url),
                },
                {
                    "rel": "parent",
                    "href": str(
                        request.url_for(
                            "catalog", topic_name=topic_name
                        ).include_query_params(token=token)
                    ),
                },
            ]
        )
    return collection
