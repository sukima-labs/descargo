"""``descargo profile``: list, validate and inspect institution profiles."""

import json
from pathlib import Path
from typing import Annotated, Any, Literal

import typer
import yaml

from descargo.cli.common import fail
from descargo.core.data import data_dir
from descargo.core.profiles import (
    ProfileError,
    UnknownNodeError,
    find_profile,
    load_profile,
    profile_paths,
    resolve,
    unverified_facts,
)
from descargo.i18n import t

app = typer.Typer(
    help="List, validate and show institution profiles.",
    no_args_is_help=True,
    rich_markup_mode=None,
)

ProfilesDir = Annotated[
    Path | None,
    typer.Option(
        "--profiles-dir",
        help="Folder with <country>/<institution>.yaml files. Defaults to the bundled ones.",
        file_okay=False,
        exists=True,
    ),
]


def _root(profiles_dir: Path | None) -> Path:
    return profiles_dir if profiles_dir is not None else data_dir("profiles")


@app.command("list")
def list_profiles(profiles_dir: ProfilesDir = None) -> None:
    """List available profiles with their count of unverified facts."""
    root = _root(profiles_dir)
    paths = profile_paths(root)
    if not paths:
        typer.echo(t("profile.none_found", root=root))
        return
    for path in paths:
        try:
            profile = load_profile(path, root=root)
        except ProfileError as exc:
            typer.echo(f"{t('profile.invalid', path=path)}: {'; '.join(exc.problems)}")
            continue
        pending = len(unverified_facts(profile))
        typer.echo(f"{profile.id}\t{profile.institution.name}\t{pending}")


@app.command()
def validate(
    files: Annotated[
        list[Path] | None,
        typer.Argument(help="Profile files. Defaults to every profile in --profiles-dir."),
    ] = None,
    profiles_dir: ProfilesDir = None,
) -> None:
    """Validate profiles against the schema. Exits with status 1 if any is invalid."""
    root = _root(profiles_dir)
    paths = files or profile_paths(root)
    invalid = 0
    for path in paths:
        try:
            load_profile(path, root=None if files else root)
        except ProfileError as exc:
            invalid += 1
            typer.echo(t("profile.invalid", path=path))
            for problem in exc.problems:
                typer.echo(f"  - {problem}")
        else:
            typer.echo(t("profile.valid", path=path))
    typer.echo(t("profile.summary", valid=len(paths) - invalid, invalid=invalid))
    if invalid:
        raise typer.Exit(code=1)


@app.command()
def show(
    profile_id: Annotated[str, typer.Argument(help="Profile id, e.g. 'es/uah'.")],
    path: Annotated[
        str | None,
        typer.Option("--path", help="faculty[/degree[/course]] ids to resolve policies for."),
    ] = None,
    output_format: Annotated[
        Literal["yaml", "json"], typer.Option("--format", help="Output format.")
    ] = "yaml",
    profiles_dir: ProfilesDir = None,
) -> None:
    """Show the policies that apply at one level of a profile."""
    try:
        profile = find_profile(_root(profiles_dir), profile_id)
        resolved = resolve(profile, path)
    except (FileNotFoundError, ProfileError, UnknownNodeError) as exc:
        raise fail(str(exc)) from exc
    document: dict[str, Any] = {
        "profile": profile.id,
        "institution": profile.institution.name,
        "chain": list(resolved.chain),
        "policies": resolved.policies.model_dump(mode="json", exclude_none=True),
        "origins": {name: list(ids) for name, ids in resolved.origins.items()},
    }
    if output_format == "json":
        typer.echo(json.dumps(document, indent=2, ensure_ascii=False))
    else:
        typer.echo(yaml.safe_dump(document, allow_unicode=True, sort_keys=False).rstrip())


@app.command()
def unverified(
    profile_id: Annotated[
        str | None, typer.Argument(help="Profile id. Defaults to every profile.")
    ] = None,
    profiles_dir: ProfilesDir = None,
) -> None:
    """List facts still marked needs_verification, so a human can check them."""
    root = _root(profiles_dir)
    try:
        profiles = (
            [find_profile(root, profile_id)]
            if profile_id
            else [load_profile(p, root=root) for p in profile_paths(root)]
        )
    except (FileNotFoundError, ProfileError) as exc:
        raise fail(str(exc)) from exc
    for profile in profiles:
        pending = unverified_facts(profile)
        if not pending:
            typer.echo(t("profile.all_verified", profile=profile.id))
            continue
        typer.echo(t("profile.unverified_header", profile=profile.id, count=len(pending)))
        for item in pending:
            typer.echo(t("profile.unverified_item", location=item.location))
