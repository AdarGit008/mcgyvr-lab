# The lab's part of a split test file. The tests of this file that are the
# product's were removed here; they remain in the product's file at this path.
"""The rig is held to its docker version, by gate 2 and again by gate 3.

The same image can list ``Vulkan0`` on one rig and bench the CPU on another,
with identical driver libraries injected, when the dockers differ: a docker
that routes ``--gpus all`` through the CDI spec mounts the NVIDIA Vulkan ICD
manifest, and one that routes it through the legacy hook does not. A comparison
between two rigs is only sound if something states which docker each runs.

``hosts.json[host].rig.docker`` states it. The reader gate 2 ships to the rig
(``rig-snapshot.sh:docker_version``) prints the daemon's version beside the
hardware and refuses rather than guesses when it cannot; gate 2 (``02-rig.py``)
compares it with the declaration like every other key. Gate 3 (``03-image.py``)
then asks the daemon the door's ``docker`` reaches — the rig's, over ``-H
ssh://HOST`` — for its name and version: the daemon a tag is resolved through
must be the machine gate 2 read, on the docker hosts.json declares.
"""

from __future__ import annotations

import json

import pytest

from tests import onedoor

DOCKER = "29.7.2"


@pytest.mark.parametrize("host", ["srv1", "srv2"])
def test_hosts_json_declares_docker_for_each_rig(host: str) -> None:
    document = json.loads(onedoor.HOSTS_JSON.read_text(encoding="utf-8"))
    rig = document[host]["rig"]
    assert rig.get("docker") == DOCKER, (
        f"hosts.json[{host!r}].rig.docker is {rig.get('docker')!r}; both rigs "
        f"run docker-ce {DOCKER}"
    )
