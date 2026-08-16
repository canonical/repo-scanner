# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The command base carrying reposcan's flow-down global parameters.

Every leaf command subclasses this, so `self.backend`/`self.verbosity`/`self.uid`/
`self.image` are available (typed) in every `run`, and the globals may be given
anywhere on the command line (`--backend`, `-v`/`--verbosity`, `--uid`, `--image`),
via env (REPOSCAN_<NAME>), or in the config file. Each parameter's long flag is
inferred from its name, so only the short `-v` is spelled out here.
"""

from repo_scanner.backends import BACKEND_NAMES
from repo_scanner.cli.engine.resolve import LOG_LEVELS, parse_image, parse_uid
from repo_scanner.cli.spec import Command as _Command
from repo_scanner.cli.spec import option


class Command(_Command):
    backend: str = option(
        default="auto",
        choices=BACKEND_NAMES,
        config=True,
        help="The execution backend tools run in.",
    )
    verbosity: str = option(
        extra_flags="-v",
        default="info",
        choices=tuple(LOG_LEVELS),
        config=True,
        help="The lowest log level written to stderr.",
    )
    uid: int | None = option(
        convert=parse_uid,
        config=True,
        help="UID for in-backend processes; unset runs as the invoking host user.",
    )
    image: str | None = option(
        convert=parse_image,
        config=True,
        help="The tool image to run: an OCI reference, or the 'canonical' shorthand.",
    )
