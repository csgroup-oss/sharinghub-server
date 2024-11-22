# Copyright 2024, CS GROUP - France, https://www.csgroup.eu/
#
# This file is part of SharingHub project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import contextlib
from typing import Any

import requests
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from . import merge


def openapi_aggregator(app: FastAPI, services_conf: dict[str, dict[str, Any]]) -> None:
    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        # Generate app own openapi schema
        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            summary=app.summary,
            description=app.description,
            routes=app.routes,
        )

        # Prune paths that were replaced by services
        services_paths = [s["path"] for s in services_conf.values()]
        prune_openapi_schema_paths(openapi_schema, services_paths)

        # Build openapi schema from services
        services = resolve_services(services_conf)
        services_openapi_schema = build_openapi_schema(services)

        # Merge own openapi schema with the services
        # Own schema is given second for update priority.
        openapi_schema = merge(services_openapi_schema, openapi_schema)

        # Inject generated description
        openapi_schema["info"]["description"] = (
            app.description + services_openapi_schema["info"]["description"]
        )

        # Remove services status
        services_status_paths = [s["status-path"] for s in services_conf.values()]
        prune_openapi_schema_paths(openapi_schema, services_status_paths)

        # Set app's openapi_schema for caching
        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi  # type: ignore[method-assign]


def prune_openapi_schema_paths(
    openapi_schema: dict[str, Any], paths: list[str]
) -> None:
    for prefix_path in paths:
        openapi_paths = openapi_schema["paths"]
        for path in [*openapi_paths]:
            if path.startswith(prefix_path):
                openapi_paths.pop(path)


def resolve_services(services_conf: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    services: list[dict[str, Any]] = []
    for service in services_conf.values():
        response = requests.get(service["openapi"], timeout=10)
        if response.ok:
            with contextlib.suppress(requests.JSONDecodeError):
                services.append({**service, "openapi_schema": response.json()})
    return services


def build_openapi_schema(
    services: list[dict[str, Any]],
) -> dict[str, Any]:
    openapi_schema: dict[str, Any] = {"info": {"description": ""}}
    if services:
        openapi_description = "\n## Services\n"

        for service in services:
            service_path = service["path"]
            service_openapi_schema = service["openapi_schema"]

            patch_openapi_schema_paths(service_openapi_schema, service_path)
            openapi_schema = merge(openapi_schema, service_openapi_schema)
            openapi_description += create_service_description(service_openapi_schema)

        # Override description with the one created
        openapi_schema["info"]["description"] = openapi_description.rstrip()

        # Remove servers (used by services for their sub path)
        openapi_schema.pop("servers", None)

    return openapi_schema


def patch_openapi_schema_paths(
    openapi_schema: dict[str, Any], service_path: str
) -> None:
    openapi_schema.pop("servers", None)
    openapi_paths = openapi_schema.get("paths", {})
    for path in [*openapi_paths]:
        openapi_paths[f"{service_path}{path}"] = openapi_paths.pop(path)


def create_service_description(openapi_schema: dict[str, Any]) -> str:
    info = openapi_schema.get("info", {})
    title = info.get("title", "").strip()
    description = info.get("description", "").strip()
    version = info.get("version", "undefined").strip()
    if title and description:
        return f"\n### {title} <small>({version})</small>\n{description}\n"
    return ""
