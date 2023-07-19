from fastapi import Request
from fastapi.exceptions import HTTPException
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRouter

from .config import GITLAB_API_URL, GITLAB_TOPICS, GITLAB_URL
from .gitlab import GitlabClient
from .utils import is_local, make_description_from_readme, parse_markdown, slugify

router = APIRouter(prefix="/{token}", tags=["stac"])


@router.get("/")
async def index(request: Request, token: str):
    return RedirectResponse(request.url_for("root_catalog", token=token))


@router.get("/catalog.json")
async def root_catalog(request: Request, token: str):
    topics_catalogs = [
        {
            "rel": "child",
            "href": str(
                request.url_for("topic_catalog", token=token, topic_name=topic_name)
            ),
        }
        for topic_name in GITLAB_TOPICS
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


@router.get("/{topic_name:str}/catalog.json")
async def topic_catalog(request: Request, token: str, topic_name: str):
    links = []

    topic = GITLAB_TOPICS.get(topic_name)
    if not topic:
        raise HTTPException(
            status_code=404, detail=f"Topic '{topic_name}' not configured"
        )

    topic_title = topic.get("title", topic_name)
    topic_description = topic.get(
        "description",
        f"{topic_title} catalog generated from your [Gitlab]({GITLAB_URL}) repositories with STAC Dataset Proxy.",
    )

    gitlab_client = GitlabClient(GITLAB_API_URL, token)
    projects = await gitlab_client.get_projects(topic_name)

    for project in projects:
        links.append(
            {
                "rel": "child",
                "href": str(
                    request.url_for(
                        "collection",
                        token=token,
                        topic_name=topic_name,
                        project_path=project["path_with_namespace"],
                    )
                ),
            }
        )

    return {
        "stac_version": "1.0.0",
        "type": "Catalog",
        "id": f"gitlab-{slugify(topic_name)}-stac-catalog",
        "title": topic_title,
        "description": topic_description,
        "links": [
            {
                "rel": "root",
                "href": str(request.url_for("root_catalog", token=token)),
            },
            {
                "rel": "self",
                "href": str(request.url),
            },
            {
                "rel": "parent",
                "href": str(request.url_for("root_catalog", token=token)),
            },
            *links,
        ],
    }


@router.get("/{topic_name:str}/{project_path:path}/collection.json")
async def collection(request: Request, token: str, topic_name: str, project_path: str):
    gitlab_client = GitlabClient(GITLAB_API_URL, token)
    project, readme = await gitlab_client.get_project_readme(project_path)
    readme_doc, readme_xml, readme_metadata = parse_markdown(readme)

    description = make_description_from_readme(readme_doc)
    extent = readme_metadata.get("extent", {})
    spatial_bbox = extent.get("bbox", [[-180, -90, 180, 90]])
    temporal_interval = extent.get(
        "temporal", [[project["created_at"], project["last_activity_at"]]]
    )

    if "license" in readme_metadata:
        license = readme_metadata["license"]
        license_url = readme_metadata.get("license_url")
    elif project["license_url"]:
        license = project["license"]["key"]
        license_url = project["license_url"]
    else:
        license = "proprietary"
        license_url = None

    keywords = readme_metadata.get("keywords", [])
    topic_keyword = slugify(topic_name)
    if topic_keyword not in keywords:
        keywords.append(topic_keyword)

    collection = {
        "stac_version": "1.0.0",
        "stac_extensions": ["collection-assets"],
        "type": "Collection",
        "id": f"gitlab-{slugify(project['name_with_namespace'])}",
        "title": project["name_with_namespace"],
        "description": description,
        "keywords": keywords,
        "license": license,
        "providers": [
            {
                "name": "GitLab",
                "roles": ["host"],
                "url": GITLAB_URL,
            }
        ],
        "extent": {
            "spatial": {"bbox": spatial_bbox},
            "temporal": {"interval": temporal_interval},
        },
        "links": [
            {
                "rel": "root",
                "href": str(request.url_for("root_catalog", token=token)),
            },
            {
                "rel": "self",
                "href": str(request.url),
            },
            {
                "rel": "parent",
                "href": str(
                    request.url_for("topic_catalog", token=token, topic_name=topic_name)
                ),
            },
            {
                "rel": "license",
                "href": license_url,
            },
        ],
    }

    preview = project["avatar_url"]
    preview = readme_metadata.get("preview", preview)
    preview = readme_metadata.get("thumbnail", preview)
    for img in readme_xml.xpath("//img"):
        if img.get("alt").lower().strip() in ["preview", "thumbnail"]:
            preview = img.get("src")
    if is_local(preview):
        preview = (
            f"{GITLAB_URL}/{project_path}/raw/{project['default_branch']}/{preview}"
        )
    if preview:
        collection["links"].append(
            {
                "rel": "preview",
                "href": preview,
            }
        )

    return collection
