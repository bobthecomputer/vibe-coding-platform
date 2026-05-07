#!/bin/sh
set -eu
RUNTIME=/volume1/Saclay/projects/syntelos/runtime
BIN="$RUNTIME/bin"
HOME_DIR="$RUNTIME/home"
HERMES_HOME="$HOME_DIR/.hermes"
INSTALL="$RUNTIME/hermes-agent"
DOWNLOADS="$RUNTIME/downloads"
TARBALL="$DOWNLOADS/hermes-agent-main.tgz"
mkdir -p "$BIN" "$HOME_DIR" "$HERMES_HOME" "$DOWNLOADS"
export HOME="$HOME_DIR"
export HERMES_HOME="$HERMES_HOME"
export PATH="$BIN:$PATH"
if [ ! -x "$BIN/uv" ]; then
  echo "Installing uv into $BIN"
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$BIN" HOME="$HOME_DIR" sh
fi
"$BIN/uv" --version
if [ ! -f "$TARBALL" ] || [ ! -s "$TARBALL" ]; then
  echo "Downloading Hermes source tarball"
  curl -L --fail --connect-timeout 30 --max-time 180 -o "$TARBALL.tmp" https://api.github.com/repos/NousResearch/hermes-agent/tarball/main
  mv "$TARBALL.tmp" "$TARBALL"
fi
rm -rf "$INSTALL.tmp"
mkdir -p "$INSTALL.tmp"
python3 - <<'PY'
import tarfile, shutil
from pathlib import Path
runtime=Path('/volume1/Saclay/projects/syntelos/runtime')
tarball=runtime/'downloads'/'hermes-agent-main.tgz'
tmp=runtime/'hermes-agent.tmp'
install=runtime/'hermes-agent'
with tarfile.open(tarball, 'r:gz') as archive:
    members=archive.getmembers()
    roots={m.name.split('/',1)[0] for m in members if m.name}
    if len(roots)!=1:
        raise SystemExit('unexpected tarball layout')
    root=next(iter(roots))
    target_root=tmp.resolve()
    for m in members:
        target=(tmp/m.name).resolve()
        if not str(target).startswith(str(target_root)):
            raise SystemExit('unsafe tar member')
    archive.extractall(tmp)
extracted=tmp/root
backup=runtime/'hermes-agent.previous'
if backup.exists():
    shutil.rmtree(backup)
if install.exists():
    install.rename(backup)
extracted.rename(install)
shutil.rmtree(tmp, ignore_errors=True)
PY
cd "$INSTALL"
"$BIN/uv" python install 3.11
"$BIN/uv" venv venv --python 3.11
VIRTUAL_ENV="$INSTALL/venv" "$BIN/uv" pip install -e .
mkdir -p "$HERMES_HOME"/cron "$HERMES_HOME"/sessions "$HERMES_HOME"/logs "$HERMES_HOME"/pairing "$HERMES_HOME"/hooks "$HERMES_HOME"/image_cache "$HERMES_HOME"/audio_cache "$HERMES_HOME"/memories "$HERMES_HOME"/skills
[ -f "$HERMES_HOME/.env" ] || touch "$HERMES_HOME/.env"
if [ ! -f "$HERMES_HOME/config.yaml" ] && [ -f "$INSTALL/cli-config.yaml.example" ]; then
  cp "$INSTALL/cli-config.yaml.example" "$HERMES_HOME/config.yaml"
fi
cat > "$BIN/hermes" <<'SH'
#!/bin/sh
RUNTIME=/volume1/Saclay/projects/syntelos/runtime
export HOME="$RUNTIME/home"
export HERMES_HOME="$RUNTIME/home/.hermes"
export PATH="$RUNTIME/bin:$PATH"
exec "$RUNTIME/hermes-agent/venv/bin/hermes" "$@"
SH
chmod +x "$BIN/hermes"
"$BIN/hermes" --version
