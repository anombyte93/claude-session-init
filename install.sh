#!/usr/bin/env bash
# ============================================================================
# Atlas Session Lifecycle — Installer
# ============================================================================
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/anombyte93/atlas-session-lifecycle/main/install.sh | bash
#   curl -fsSL ... | bash -s -- --plugin          # install as Claude Code plugin
#   bash install.sh                                # skill mode (default)
#   bash install.sh --plugin                       # plugin mode
#   bash install.sh --version v1                   # install v1 (legacy)
#   bash install.sh --revert                       # revert to v1
#   bash install.sh --update                       # pull latest and reinstall
#   bash install.sh --check-update                 # check for newer version
#   bash install.sh --no-extras                    # skip bundled extra skills
#   bash install.sh --all                          # install all extras without prompting
# ============================================================================

set -euo pipefail

REPO_OWNER="anombyte93"
REPO_NAME="atlas-session-lifecycle"
SKILL_NAME="start"
VERSION="2.0.0"
SKILL_DIR="${SKILL_DIR:-${HOME}/.claude/skills/${SKILL_NAME}}"
PLUGIN_DIR="${HOME}/.claude/plugins/${REPO_NAME}"
TEMPLATE_DIR="${HOME}/claude-session-init-templates"

UPDATES_DIR="${HOME}/.config/claude-skills"
UPDATES_FILE="${UPDATES_DIR}/updates.json"
UPDATE_INTERVAL_SECONDS=86400
GITHUB_API="https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/releases/latest"
CLONE_URL="https://github.com/${REPO_OWNER}/${REPO_NAME}.git"

if [[ -t 1 ]] && [[ -z "${CI:-}" ]] && [[ -z "${NO_COLOR:-}" ]]; then
    RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'
    CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
else
    RED='' GREEN='' YELLOW='' CYAN='' BOLD='' RESET=''
fi

info()  { printf "${CYAN}[info]${RESET}  %s\n" "$*"; }
ok()    { printf "${GREEN}[ok]${RESET}    %s\n" "$*"; }
warn()  { printf "${YELLOW}[warn]${RESET}  %s\n" "$*"; }
err()   { printf "${RED}[error]${RESET} %s\n" "$*" >&2; }
die()   { err "$@"; exit 1; }

cleanup() {
    if [[ -n "${TMPDIR_SKILL:-}" ]] && [[ -d "${TMPDIR_SKILL}" ]]; then
        rm -rf "${TMPDIR_SKILL}"
    fi
}
trap cleanup EXIT

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

check_update() {
    if [[ -n "${CI:-}" ]] || [[ -n "${NO_UPDATE_CHECK:-}" ]]; then return 0; fi
    require_cmd curl; require_cmd date; mkdir -p "${UPDATES_DIR}"
    if [[ -f "${UPDATES_FILE}" ]]; then
        local last_check; last_check=$(python3 -c "
import json
try:
    d = json.load(open('${UPDATES_FILE}'))
    print(d.get('skills', {}).get('${SKILL_NAME}', {}).get('last_check', 0))
except: print(0)
" 2>/dev/null || echo 0)
        local now; now=$(date +%s); local elapsed=$(( now - last_check ))
        if [[ ${elapsed} -lt ${UPDATE_INTERVAL_SECONDS} ]]; then
            local cached_latest; cached_latest=$(python3 -c "
import json
try:
    d = json.load(open('${UPDATES_FILE}'))
    print(d.get('skills', {}).get('${SKILL_NAME}', {}).get('latest', ''))
except: print('')
" 2>/dev/null || echo "")
            if [[ -n "${cached_latest}" ]] && [[ "${cached_latest}" != "${VERSION}" ]]; then
                warn "Update available: ${VERSION} -> ${cached_latest}"
                info "Run: curl -fsSL https://raw.githubusercontent.com/${REPO_OWNER}/${REPO_NAME}/main/install.sh | bash"
            fi; return 0
        fi
    fi
    local api_response; api_response=$(curl -fsSL --max-time 5 -H "Accept: application/vnd.github+json" "${GITHUB_API}" 2>/dev/null) || return 0
    local latest_version; latest_version=$(printf '%s' "${api_response}" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin); tag = data.get('tag_name', ''); print(tag.lstrip('v'))
except: print('')
" 2>/dev/null || echo "")
    if [[ -z "${latest_version}" ]]; then return 0; fi
    local now; now=$(date +%s)
    python3 -c "
import json
path = '${UPDATES_FILE}'
try: data = json.load(open(path))
except: data = {}
data.setdefault('skills', {})
data['skills']['${SKILL_NAME}'] = {'last_check': ${now}, 'latest': '${latest_version}', 'current': '${VERSION}'}
with open(path, 'w') as f: json.dump(data, f, indent=2)
" 2>/dev/null || true
    if [[ "${latest_version}" != "${VERSION}" ]]; then
        warn "Update available: ${VERSION} -> ${latest_version}"
        info "Run: curl -fsSL https://raw.githubusercontent.com/${REPO_OWNER}/${REPO_NAME}/main/install.sh | bash"
    else ok "You are on the latest version (${VERSION})"; fi
}

revert_to_v1() {
    info "Reverting to v1 (monolithic SKILL.md, no script)"

    if [[ ! -d "${SKILL_DIR}" ]]; then
        die "No installation found at ${SKILL_DIR}. Nothing to revert."
    fi

    TMPDIR_SKILL=$(mktemp -d "${TMPDIR:-/tmp}/claude-skill-XXXXXX")
    info "Cloning ${REPO_OWNER}/${REPO_NAME}..."
    git clone --depth 1 --quiet "${CLONE_URL}" "${TMPDIR_SKILL}/repo" 2>/dev/null \
        || die "Failed to clone repository."

    local src_dir="${TMPDIR_SKILL}/repo"

    if [[ ! -f "${src_dir}/v1/SKILL.md" ]]; then
        die "v1/SKILL.md not found in repository. Cannot revert."
    fi

    # Back up current v2 files
    if [[ -f "${SKILL_DIR}/SKILL.md" ]]; then
        cp "${SKILL_DIR}/SKILL.md" "${SKILL_DIR}/SKILL.md.v2-backup"
        ok "Backed up v2 SKILL.md -> SKILL.md.v2-backup"
    fi
    if [[ -f "${SKILL_DIR}/session-init.py" ]]; then
        cp "${SKILL_DIR}/session-init.py" "${SKILL_DIR}/session-init.py.v2-backup"
        ok "Backed up session-init.py -> session-init.py.v2-backup"
    fi

    # Install v1 SKILL.md
    cp "${src_dir}/v1/SKILL.md" "${SKILL_DIR}/SKILL.md"
    ok "Installed v1 SKILL.md (monolithic)"

    # Remove session-init.py (v1 doesn't use it)
    if [[ -f "${SKILL_DIR}/session-init.py" ]]; then
        rm "${SKILL_DIR}/session-init.py"
        ok "Removed session-init.py (not used by v1)"
    fi

    local timestamp; timestamp=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
    cat > "${SKILL_DIR}/.version" <<VEOF
${VERSION}-v1
installed: ${timestamp}
mode: revert
repo: ${REPO_OWNER}/${REPO_NAME}
skill_version: v1
VEOF
    ok "Wrote .version (${VERSION}-v1, ${timestamp})"

    printf "\n"
    printf "${GREEN}${BOLD}Successfully reverted to v1${RESET}\n"
    printf "  Location: %s\n" "${SKILL_DIR}"
    printf "  Note: v2 files backed up with .v2-backup extension\n"
    printf "\n"
}

install_plugin() {
    local mode="install"

    info "Atlas Session Lifecycle — Plugin Installer"
    info "Version: ${BOLD}v${VERSION}${RESET}"
    printf "\n"; require_cmd git

    if [[ -d "${PLUGIN_DIR}" ]]; then
        mode="upgrade"
        info "Existing plugin installation detected"
        info "Mode: upgrade (pulling latest)"

        cd "${PLUGIN_DIR}"
        git fetch --quiet origin main 2>/dev/null || true
        git reset --hard origin/main --quiet 2>/dev/null || {
            warn "Git pull failed, doing fresh clone"
            cd "${HOME}"
            rm -rf "${PLUGIN_DIR}"
            mode="install"
        }

        if [[ "${mode}" == "upgrade" ]]; then
            local timestamp; timestamp=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
            ok "Updated plugin to latest (${timestamp})"
            printf "\n"
            printf "${GREEN}${BOLD}Successfully upgraded atlas-session-lifecycle plugin${RESET}\n"
            printf "  Location: %s\n" "${PLUGIN_DIR}"
            printf "\n"
            info "To use: ${CYAN}/start${RESET}"
            printf "\n"
            return 0
        fi
    fi

    if [[ "${mode}" == "install" ]]; then
        info "Mode: fresh install"
        mkdir -p "$(dirname "${PLUGIN_DIR}")"
        git clone --quiet "${CLONE_URL}" "${PLUGIN_DIR}" 2>/dev/null \
            || die "Failed to clone repository."
        ok "Cloned plugin to ${PLUGIN_DIR}"
    fi

    # Also install templates to home dir fallback
    if [[ -d "${PLUGIN_DIR}/templates" ]]; then
        mkdir -p "${TEMPLATE_DIR}"
        cp "${PLUGIN_DIR}/templates/"* "${TEMPLATE_DIR}/" 2>/dev/null || true
        ok "Installed templates to ${TEMPLATE_DIR}/ (fallback)"
    fi

    printf "\n"
    printf "${GREEN}${BOLD}Successfully installed atlas-session-lifecycle plugin${RESET}\n"
    printf "  Location: %s\n" "${PLUGIN_DIR}"
    printf "  Templates: %s\n" "${TEMPLATE_DIR}"
    printf "\n"
    info "To use: ${CYAN}/start${RESET}"
    printf "\n"
}

install_extra_skills() {
    # Discover and install bundled skills beyond /start
    # $1 = src_dir (cloned repo), $2 = "all"|"ask"|"none"
    local src_dir="$1"
    local extras_mode="${2:-ask}"
    local skills_base="${HOME}/.claude/skills"

    if [[ "${extras_mode}" == "none" ]]; then return 0; fi

    # Discover extra skills (everything in skills/ except start/)
    local extras=()
    local descriptions=()
    if [[ -d "${src_dir}/skills" ]]; then
        for skill_dir in "${src_dir}/skills"/*/; do
            local skill_name; skill_name=$(basename "${skill_dir}")
            if [[ "${skill_name}" == "start" ]]; then continue; fi
            if [[ -f "${skill_dir}/SKILL.md" ]]; then
                extras+=("${skill_name}")
                # Extract description from YAML frontmatter
                local desc; desc=$(sed -n 's/^description: *"\{0,1\}\(.*\)"\{0,1\}$/\1/p' "${skill_dir}/SKILL.md" | head -1)
                descriptions+=("${desc:-No description}")
            fi
        done
    fi

    if [[ ${#extras[@]} -eq 0 ]]; then return 0; fi

    printf "\n"
    info "Bundled extra skills available:"
    printf "\n"
    for i in "${!extras[@]}"; do
        printf "  ${BOLD}%d)${RESET} ${CYAN}/%s${RESET}\n" "$((i+1))" "${extras[$i]}"
        printf "     %s\n" "${descriptions[$i]:0:100}"
    done
    printf "\n"

    local install_extras=()

    if [[ "${extras_mode}" == "all" ]]; then
        install_extras=("${extras[@]}")
        info "Installing all extra skills (--all)"
    elif [[ -t 0 ]] && [[ -t 1 ]]; then
        # Interactive — ask the user
        printf "Install extra skills? [${BOLD}a${RESET}]ll / [${BOLD}n${RESET}]one / [${BOLD}s${RESET}]elect: "
        local choice; read -r choice
        case "${choice}" in
            a|A|all|ALL|"")
                install_extras=("${extras[@]}") ;;
            n|N|none|NONE)
                info "Skipping extra skills"
                return 0 ;;
            s|S|select|SELECT)
                for i in "${!extras[@]}"; do
                    printf "  Install ${CYAN}/%s${RESET}? [Y/n]: " "${extras[$i]}"
                    local yn; read -r yn
                    case "${yn}" in
                        n|N|no|NO) ;;
                        *) install_extras+=("${extras[$i]}") ;;
                    esac
                done ;;
            *)
                info "Skipping extra skills"
                return 0 ;;
        esac
    else
        # Non-interactive (piped via curl) — install all by default
        install_extras=("${extras[@]}")
        info "Installing all extra skills (non-interactive)"
    fi

    # Install selected extras
    for skill_name in "${install_extras[@]}"; do
        local target="${skills_base}/${skill_name}"
        mkdir -p "${target}"
        cp "${src_dir}/skills/${skill_name}/SKILL.md" "${target}/SKILL.md"
        ok "Installed /${skill_name} to ${target}/"
    done

    if [[ ${#install_extras[@]} -gt 0 ]]; then
        printf "\n"
        ok "Installed ${#install_extras[@]} extra skill(s)"
    fi
}

install_skill() {
    local target_version="${1:-v2}"
    local extras_mode="${2:-ask}"
    local mode="install"

    info "Atlas Session Lifecycle — Skill Installer"
    info "Skill: ${BOLD}${SKILL_NAME}${RESET} v${VERSION} (${target_version})"
    printf "\n"; require_cmd git

    if [[ -d "${SKILL_DIR}" ]]; then
        mode="upgrade"
        local existing_version="unknown"
        if [[ -f "${SKILL_DIR}/.version" ]]; then
            existing_version=$(head -1 "${SKILL_DIR}/.version" 2>/dev/null || echo "unknown")
        fi
        info "Existing installation detected (${existing_version})"
        info "Mode: upgrade"
        if [[ -f "${SKILL_DIR}/SKILL.md" ]]; then
            cp "${SKILL_DIR}/SKILL.md" "${SKILL_DIR}/SKILL.md.bak"
            ok "Backed up SKILL.md -> SKILL.md.bak"
        fi
    else info "Mode: fresh install"; fi

    TMPDIR_SKILL=$(mktemp -d "${TMPDIR:-/tmp}/claude-skill-XXXXXX")
    info "Cloning ${REPO_OWNER}/${REPO_NAME}..."
    git clone --depth 1 --quiet "${CLONE_URL}" "${TMPDIR_SKILL}/repo" 2>/dev/null \
        || die "Failed to clone repository."

    local src_dir="${TMPDIR_SKILL}/repo"

    mkdir -p "${SKILL_DIR}"

    if [[ "${target_version}" == "v1" ]]; then
        # v1 install: monolithic SKILL.md, no script
        if [[ -f "${src_dir}/v1/SKILL.md" ]]; then
            cp "${src_dir}/v1/SKILL.md" "${SKILL_DIR}/SKILL.md"
            ok "Installed v1 SKILL.md (monolithic)"
        else
            die "v1/SKILL.md not found in repository."
        fi
        if [[ -f "${SKILL_DIR}/session-init.py" ]]; then
            rm "${SKILL_DIR}/session-init.py"
            ok "Removed session-init.py (not used by v1)"
        fi
    else
        # v2 install: skill from skills/start/, script from scripts/
        if [[ -f "${src_dir}/skills/start/SKILL.md" ]]; then
            cp "${src_dir}/skills/start/SKILL.md" "${SKILL_DIR}/SKILL.md"
            ok "Installed SKILL.md (orchestrator)"
        else
            die "skills/start/SKILL.md not found in repository."
        fi

        if [[ -f "${src_dir}/scripts/session-init.py" ]]; then
            cp "${src_dir}/scripts/session-init.py" "${SKILL_DIR}/session-init.py"
            chmod +x "${SKILL_DIR}/session-init.py"
            ok "Installed session-init.py (backend)"
        else
            die "scripts/session-init.py not found in repository."
        fi

        # Deploy MCP server source (atlas-session MCP package)
        if [[ -d "${src_dir}/src/atlas_session" ]]; then
            mkdir -p "${SKILL_DIR}/src"
            rm -rf "${SKILL_DIR}/src/atlas_session"
            cp -r "${src_dir}/src/atlas_session" "${SKILL_DIR}/src/atlas_session"
            if [[ -f "${src_dir}/src/pyproject.toml" ]]; then
                cp "${src_dir}/src/pyproject.toml" "${SKILL_DIR}/src/pyproject.toml"
            fi
            ok "Installed MCP server (src/atlas_session/)"
        else
            warn "src/atlas_session/ not found — MCP server not installed"
        fi
    fi

    # Install templates
    if [[ -d "${src_dir}/templates" ]]; then
        mkdir -p "${TEMPLATE_DIR}"
        cp "${src_dir}/templates/"* "${TEMPLATE_DIR}/" 2>/dev/null || true
        ok "Installed templates to ${TEMPLATE_DIR}/"
    fi

    if [[ -f "${src_dir}/install.sh" ]]; then
        cp "${src_dir}/install.sh" "${SKILL_DIR}/install.sh"
        chmod +x "${SKILL_DIR}/install.sh"
    fi

    # Offer extra bundled skills (v2 only)
    if [[ "${target_version}" == "v2" ]]; then
        install_extra_skills "${src_dir}" "${extras_mode}"
    fi

    local timestamp; timestamp=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
    cat > "${SKILL_DIR}/.version" <<VEOF
${VERSION}
installed: ${timestamp}
mode: ${mode}
repo: ${REPO_OWNER}/${REPO_NAME}
skill_version: ${target_version}
VEOF
    ok "Wrote .version (${VERSION}, ${timestamp})"

    # Clean up old flat file if it exists
    if [[ -f "${HOME}/.claude/skills/start.md" ]]; then
        rm "${HOME}/.claude/skills/start.md"
        ok "Removed old flat file start.md"
    fi

    printf "\n"
    printf "${GREEN}${BOLD}Successfully %s ${SKILL_NAME} v${VERSION} (${target_version})${RESET}\n" \
        "$([ "${mode}" = "upgrade" ] && echo "upgraded" || echo "installed")"
    printf "  Location: %s\n" "${SKILL_DIR}"
    printf "  Templates: %s\n" "${TEMPLATE_DIR}"
    if [[ "${target_version}" == "v2" ]]; then
        printf "  Script: %s/session-init.py\n" "${SKILL_DIR}"
    fi
    printf "\n"
    info "To use: ${CYAN}/start${RESET}"
    printf "\n"
}

main() {
    local target_version="v2"
    local install_mode="skill"
    local extras_mode="ask"

    # Parse modifier flags first
    local args=()
    for arg in "$@"; do
        case "${arg}" in
            --plugin) install_mode="plugin" ;;
            --no-extras) extras_mode="none" ;;
            --all) extras_mode="all" ;;
            *) args+=("${arg}") ;;
        esac
    done

    case "${args[0]:-}" in
        --check-update|-u) check_update ;;
        -v) echo "atlas-session-lifecycle v${VERSION}" ;;
        --revert) revert_to_v1 ;;
        --update)
            info "Updating atlas-session-lifecycle..."
            if [[ "${install_mode}" == "plugin" ]]; then
                install_plugin
            else
                install_skill "v2" "${extras_mode}"
            fi
            ;;
        --help|-h)
            printf "Usage: %s [OPTIONS]\n" "${0##*/}"
            printf "\n${BOLD}Atlas Session Lifecycle${RESET} — Session lifecycle management for Claude Code\n"
            printf "\nInstall modes:\n"
            printf "  (no args)          Install as skill to ~/.claude/skills/start/\n"
            printf "  --plugin           Install as plugin to ~/.claude/plugins/\n"
            printf "\nOptions:\n"
            printf "  --version v1|v2    Install specific version (skill mode only)\n"
            printf "  --revert           Revert from v2 to v1 (skill mode only)\n"
            printf "  --update           Pull latest and reinstall\n"
            printf "  --check-update     Check for newer release\n"
            printf "  --all              Install all bundled skills without prompting\n"
            printf "  --no-extras        Skip bundled extra skills (only install /start)\n"
            printf "  -v                 Print version\n"
            printf "  --help             Show help\n"
            printf "\nExamples:\n"
            printf "  # One-liner install (skill mode)\n"
            printf "  curl -fsSL https://raw.githubusercontent.com/${REPO_OWNER}/${REPO_NAME}/main/install.sh | bash\n"
            printf "\n  # One-liner install (plugin mode)\n"
            printf "  curl -fsSL https://raw.githubusercontent.com/${REPO_OWNER}/${REPO_NAME}/main/install.sh | bash -s -- --plugin\n"
            printf "\n  # Update existing installation\n"
            printf "  curl -fsSL https://raw.githubusercontent.com/${REPO_OWNER}/${REPO_NAME}/main/install.sh | bash -s -- --update\n" ;;
        "")
            if [[ "${install_mode}" == "plugin" ]]; then
                install_plugin
            else
                install_skill "v2" "${extras_mode}"
            fi
            check_update ;;
        --version)
            target_version="${args[1]:-v2}"
            if [[ "${target_version}" != "v1" ]] && [[ "${target_version}" != "v2" ]]; then
                die "Invalid version: ${target_version}. Use v1 or v2."
            fi
            install_skill "${target_version}" "${extras_mode}"
            check_update ;;
        *)
            die "Unknown argument: ${args[0]} (try --help)" ;;
    esac
}

main "$@"
