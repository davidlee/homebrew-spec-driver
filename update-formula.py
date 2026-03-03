#!/usr/bin/env python3
"""Update the Homebrew formula for a new spec-driver release.

Usage: ./update-formula.py 0.7.0
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

FORMULA = Path(__file__).parent / "Formula" / "spec-driver.rb"


def pypi_sdist(name: str, version: str) -> tuple[str, str]:
  """Return (url, sha256) for a package's sdist on PyPI."""
  api_url = f"https://pypi.org/pypi/{name}/{version}/json"
  data = json.loads(urllib.request.urlopen(api_url).read())
  for f in data["urls"]:
    if f["packagetype"] == "sdist":
      return f["url"], f["digests"]["sha256"]
  raise ValueError(f"No sdist found for {name}=={version}")


def resolve_deps(version: str) -> list[tuple[str, str]]:
  """Use uv to resolve the full dependency tree."""
  result = subprocess.run(
    ["uv", "pip", "compile", "--no-header", "-"],
    input=f"spec-driver=={version}",
    capture_output=True,
    text=True,
    check=True,
  )
  deps = []
  for line in result.stdout.splitlines():
    line = line.strip()
    if not line or line.startswith("#") or line.startswith("spec-driver=="):
      continue
    match = re.match(r"^([a-zA-Z0-9_.-]+)==([^\s\\]+)", line)
    if match:
      deps.append((match.group(1), match.group(2)))
  return deps


def build_formula(version: str) -> str:
  """Generate the complete formula."""
  url, sha256 = pypi_sdist("spec-driver", version)
  deps = resolve_deps(version)

  resources = []
  for name, ver in sorted(deps, key=lambda x: x[0].lower()):
    dep_url, dep_sha256 = pypi_sdist(name, ver)
    resources.append(
      f'  resource "{name.lower()}" do\n'
      f'    url "{dep_url}"\n'
      f'    sha256 "{dep_sha256}"\n'
      f"  end"
    )

  resource_block = "\n\n".join(resources)

  return f'''\
class SpecDriver < Formula
  include Language::Python::Virtualenv

  desc "Specification-driven development toolkit"
  homepage "https://supekku.dev/"
  url "{url}"
  sha256 "{sha256}"
  license "MIT"

  depends_on "python@3.12"

{resource_block}

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "spec-driver", shell_output("#{{bin}}/spec-driver --help")
  end
end
'''


def main():
  if len(sys.argv) != 2:
    print(f"Usage: {sys.argv[0]} <version>", file=sys.stderr)
    sys.exit(1)

  version = sys.argv[1]
  print(f"Resolving deps for spec-driver=={version}...")
  formula = build_formula(version)
  FORMULA.write_text(formula)
  print(f"Updated {FORMULA}")


if __name__ == "__main__":
  main()
