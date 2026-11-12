"""brokenbox: break-and-fix Linux troubleshooting scenarios in local KVM VMs."""
from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
import textwrap
import time

from . import config as C
from . import progress as P
from . import scenarios as S
from . import vm
from .vm import Error, log

BOLD, DIM, GREEN, RED, YELLOW, RESET = "\033[1m", "\033[2m", "\033[32m", "\033[31m", "\033[33m", "\033[0m"


def _vols(sid: str) -> tuple[str, str]:
    d = C.domain_name(sid)
    return f"{d}.qcow2", f"{d}-seed.iso"


def _scenario(sid: str) -> S.Scenario:
    try:
        return S.get(sid)
    except KeyError:
        raise Error(f"unknown scenario '{sid}'. Run `brokenbox list`.")


def _fmt_elapsed(sec: float) -> str:
    m, s = divmod(int(sec), 60)
    return f"{m}m{s:02d}s"


def _print_brief(sc: S.Scenario) -> None:
    sudo = "yes" if sc.sudo else "no"
    print(f"\n{BOLD}{sc.title}{RESET}  {DIM}[{sc.difficulty} · {sc.kind} · {sc.time_minutes} min · sudo: {sudo}]{RESET}")
    print(textwrap.indent(sc.description.strip(), "  "))
    if sc.test:
        print(f"\n  {BOLD}Test:{RESET} " + textwrap.indent(sc.test.strip(), "  ").lstrip())
    if sc.inspired_by:
        print(f"  {DIM}Inspired by: " + "\n               ".join(sc.inspired_by) + RESET)


# ---------------------------------------------------------------- commands

def cmd_doctor(a) -> None:
    ok = True

    def chk(label, cond, hint=""):
        nonlocal ok
        print(f"  {GREEN+'ok' if cond else RED+'!!'}{RESET}  {label}" + (f"  {DIM}{hint}{RESET}" if not cond and hint else ""))
        ok &= bool(cond)

    print("brokenbox doctor")
    chk("/dev/kvm accessible", os.access("/dev/kvm", os.R_OK | os.W_OK), "add yourself to the kvm group")
    for tool, pkg in [("virsh", "libvirt-clients"), ("virt-install", "virtinst"), ("xorriso", "xorriso"),
                      ("ssh", "openssh-client"), ("ssh-keygen", "openssh-client"), ("curl", "curl")]:
        chk(f"{tool} installed", shutil.which(tool), f"apt install {pkg}")
    chk(f"libvirt reachable ({C.LIBVIRT_URI})", vm.virsh("uri", check=False).returncode == 0,
        "add yourself to the libvirt group and re-login")
    chk(f"storage pool '{C.POOL}' running", "running" in vm.virsh("pool-info", C.POOL, check=False).stdout.lower())
    chk(f"network '{C.NETWORK}' active",
        "yes" in next((l for l in vm.virsh("net-info", C.NETWORK, check=False).stdout.splitlines() if l.startswith("Active")), ""),
        f"virsh net-start {C.NETWORK}")
    chk("golden image built", vm.vol_exists(C.GOLDEN_VOL), "run: brokenbox build-base")
    sys.exit(0 if ok else 1)


def cmd_build_base(a) -> None:
    vm.ensure_keys()
    running = [s.id for s in S.all_scenarios() if vm.dom_exists(C.domain_name(s.id))]
    if vm.vol_exists(C.GOLDEN_VOL) and not a.rebuild:
        log(f"golden image already exists ({C.GOLDEN_VOL}). Use --rebuild to recreate it.")
        return
    if running:
        raise Error(f"destroy scenario VMs first (they depend on the golden image): {', '.join(running)}")

    img = vm.download_cloud_image()
    if a.rebuild or not vm.vol_exists(C.CLOUD_VOL):
        log(f"uploading cloud image to pool '{C.POOL}' as {C.CLOUD_VOL}")
        vm.vol_upload(C.CLOUD_VOL, img, "qcow2")

    build = f"{C.PREFIX}-golden-build"
    seed = f"{build}-seed.iso"
    vm.dom_destroy(build)
    vm.vol_overlay(C.GOLDEN_VOL, C.CLOUD_VOL)
    vm.make_seed(seed, S.golden_user_data(vm.pubkey(C.CONTROL_KEY)), f"golden-{int(time.time())}", "brokenbox-golden")
    log("booting build VM; installing packages (this takes a few minutes)...")
    vm.dom_create(build, C.GOLDEN_VOL, seed, memory=2048, vcpus=2)
    try:
        vm.wait_shutoff(build, timeout=1800)
    except Error:
        log(f"build VM did not finish. Inspect with: virsh -c {C.LIBVIRT_URI} console {build}")
        raise
    vm.dom_destroy(build)
    vm.vol_delete(seed)
    log(f"{GREEN}golden image ready{RESET}: {C.GOLDEN_VOL}")


def _solved_cell(e: dict | None) -> str:
    best = P.best_seconds(e)
    return f"✔ {_fmt_elapsed(best)}" if best is not None else ""


def cmd_list(a) -> None:
    rows = []
    for sc in S.all_scenarios():
        st = vm.load_state(sc.id)
        state = vm.dom_state(C.domain_name(sc.id)) if st else ""
        mark = f"{GREEN}● {state}{RESET}" if state == "running" else (f"{YELLOW}● {state}{RESET}" if state else "")
        rows.append((sc.id, sc.difficulty, sc.kind, f"{sc.time_minutes}m", _solved_cell(P.get(sc.id)), sc.title, mark))
    w = [max(len(r[i]) for r in rows + [("ID", "LEVEL", "TYPE", "TIME", "SOLVED")]) for i in range(5)]
    print(f"{BOLD}{'ID':<{w[0]}}  {'LEVEL':<{w[1]}}  {'TYPE':<{w[2]}}  {'TIME':<{w[3]}}  {'SOLVED':<{w[4]}}  TITLE{RESET}")
    for r in rows:
        solved = f"{GREEN}{r[4]:<{w[4]}}{RESET}"
        print(f"{r[0]:<{w[0]}}  {r[1]:<{w[1]}}  {r[2]:<{w[2]}}  {r[3]:<{w[3]}}  {solved}  {r[5]}  {r[6]}")


def cmd_describe(a) -> None:
    _print_brief(_scenario(a.scenario))


def _run_setup(sc: S.Scenario, ip: str, verbose: bool) -> dict:
    script = S.SETUP_PRELUDE + "\n" + sc.setup_script
    p = vm.root_exec(ip, script, timeout=1800)
    if verbose or p.returncode != 0:
        sys.stderr.write(p.stdout + p.stderr)
    if p.returncode != 0:
        raise Error(f"setup for '{sc.id}' failed (exit {p.returncode})")
    expect = {}
    for line in p.stdout.splitlines():
        if line.startswith("##brokenbox:expect "):
            k, _, v = line[len("##brokenbox:expect "):].partition("=")
            expect[k] = v
    post = f"BROKENBOX_SUDO={'true' if sc.sudo else 'false'}\n" + S.POST_SETUP
    vm.root_exec(ip, post, timeout=120)
    return expect


def cmd_start(a) -> None:
    sc = _scenario(a.scenario)
    dom = C.domain_name(sc.id)
    disk, seed = _vols(sc.id)
    if not vm.vol_exists(C.GOLDEN_VOL):
        raise Error("golden image missing. Run: brokenbox build-base")
    if vm.dom_exists(dom):
        if not a.force:
            raise Error(f"'{sc.id}' already exists. Use `brokenbox ssh {sc.id}`, `reset`, or `start --force`.")
        _destroy(sc.id)

    vm.ensure_keys()
    t0 = time.time()
    log(f"creating VM {dom}")
    vm.vol_overlay(disk, C.GOLDEN_VOL)
    vm.make_seed(seed, S.user_data(sc.id, vm.pubkey(C.PLAYER_KEY), vm.pubkey(C.CONTROL_KEY)),
                 f"{sc.id}-{int(t0)}", sc.id)
    vm.dom_create(dom, disk, seed, memory=sc.memory, vcpus=sc.vcpus)
    try:
        ip = vm.dom_ip(dom)
        log(f"booting ({ip}), waiting for ssh")
        vm.wait_ssh(ip)
        vm.root_exec(ip, "cloud-init status --wait >/dev/null 2>&1 || true", timeout=600)
        vm.dom_detach_seed(dom, seed)
        vm.vol_delete(seed)
        log("breaking things (running scenario setup)")
        expect = _run_setup(sc, ip, a.verbose)
        snap = False
        if not a.no_snapshot:
            log("taking 'clean' snapshot for fast resets")
            snap = vm.virsh("snapshot-create-as", dom, "clean", "--atomic", check=False).returncode == 0
            if not snap:
                log(f"{YELLOW}snapshot failed; `reset` will rebuild the VM instead{RESET}")
    except BaseException:
        log(f"{RED}start failed{RESET}; VM left in place for debugging. Clean up with: brokenbox destroy {sc.id}")
        raise
    vm.save_state(sc.id, {"ip": ip, "expect": expect, "started_at": time.time(), "snapshot": snap, "solved": False})
    if getattr(a, "from_reset", False):
        P.bump(sc.id, "resets")
    else:
        P.bump(sc.id, "starts")
    log(f"ready in {_fmt_elapsed(time.time() - t0)}")
    _print_brief(sc)
    print(f"\n  {BOLD}Connect:{RESET} brokenbox ssh {sc.id}     {BOLD}Check:{RESET} brokenbox check {sc.id}\n")


def _state(sid: str) -> dict:
    st = vm.load_state(sid)
    if not st or not vm.dom_exists(C.domain_name(sid)):
        raise Error(f"'{sid}' is not running. Start it with: brokenbox start {sid}")
    dom = C.domain_name(sid)
    if vm.dom_state(dom) != "running":
        log(f"starting stopped VM {dom}")
        vm.virsh("start", dom)
    try:
        ip = vm.dom_ip(dom, timeout=60)
        if ip != st["ip"]:
            st["ip"] = ip
            vm.save_state(sid, st)
    except Error:
        pass
    return st


def cmd_ssh(a) -> None:
    st = _state(a.scenario)
    cmd = vm.ssh_cmd(st["ip"], a.user, C.CONTROL_KEY if a.user == "root" else C.PLAYER_KEY)
    os.execvp(cmd[0], cmd + a.command)


def cmd_check(a) -> None:
    sc = _scenario(a.scenario)
    st = _state(sc.id)
    env = "".join(f"export {k}={shlex.quote(v)}\n" for k, v in st.get("expect", {}).items())
    p = vm.root_exec(st["ip"], S.CHECK_PRELUDE + env + sc.check_script, timeout=300)
    out = (p.stdout + p.stderr).strip()
    secs = time.time() - st["started_at"]
    elapsed = _fmt_elapsed(secs)
    if p.returncode == 0:
        note = ""
        if not st.get("solved"):            # only the first passing check of a run counts
            prev = P.get(sc.id)
            prev_best = P.best_seconds(prev)
            P.record_solve(sc.id, secs, sc.time_minutes)
            st["solved"] = True
            vm.save_state(sc.id, st)
            if prev_best is None:
                note = f"  {YELLOW}first solve!{RESET}"
            elif secs < prev_best:
                note = f"  {YELLOW}new best (was {_fmt_elapsed(prev_best)}){RESET}"
        late = "" if secs <= sc.time_minutes * 60 else f" {RED}over time{RESET}{DIM}"
        print(f"{GREEN}{BOLD}✔ Solved!{RESET}  {DIM}({elapsed}, limit {sc.time_minutes}m{late}){RESET}{note}")
    else:
        if not st.get("solved"):
            P.bump(sc.id, "failed_checks")
        print(f"{RED}{BOLD}✘ Not solved yet.{RESET}  {DIM}({elapsed} elapsed){RESET}")
    if out:
        print(textwrap.indent(out, "  "))
    sys.exit(0 if p.returncode == 0 else 1)


def cmd_reset(a) -> None:
    sc = _scenario(a.scenario)
    st = vm.load_state(sc.id)
    dom = C.domain_name(sc.id)
    if st and st.get("snapshot") and vm.dom_exists(dom):
        log("reverting to 'clean' snapshot")
        vm.virsh("snapshot-revert", dom, "clean", "--running", "--force")
        vm.wait_ssh(st["ip"], timeout=120)
        # the guest clock jumped back to snapshot time; resync it to the host
        vm.root_exec(st["ip"], f"date -s @{int(time.time())} >/dev/null", timeout=30)
        st["started_at"] = time.time()
        st["solved"] = False
        vm.save_state(sc.id, st)
        P.bump(sc.id, "resets")
        log(f"{GREEN}reset done{RESET}")
    else:
        if vm.dom_exists(dom) and not st and not a.force:
            raise Error(f"VM {dom} exists but brokenbox has no state for it, so it can't be reverted. "
                        f"Use `brokenbox reset {sc.id} --force` to delete and rebuild it.")
        a.force = True
        a.from_reset = True
        cmd_start(a)


def cmd_status(a) -> None:
    any_ = False
    for sc in S.all_scenarios():
        st = vm.load_state(sc.id)
        if not st:
            continue
        any_ = True
        state = vm.dom_state(C.domain_name(sc.id))
        print(f"{sc.id:<22} {state:<10} ip={st['ip']:<16} elapsed={_fmt_elapsed(time.time() - st['started_at'])}")
    if not any_:
        print("no scenarios running")


def cmd_progress(a) -> None:
    if a.clear:
        if input("Erase all progress? Type 'yes' to confirm: ").strip() != "yes":
            print("aborted")
            return
        P.reset_all()
        print("progress cleared")
        return
    scs = S.all_scenarios()
    data = P.load()["scenarios"]
    solved = [s for s in scs if P.best_seconds(data.get(s.id)) is not None]
    print(f"{BOLD}Progress: {len(solved)}/{len(scs)} solved{RESET}")
    for level in ("easy", "medium", "hard"):
        group = [s for s in scs if s.difficulty == level]
        if group:
            n = sum(1 for s in group if s in solved)
            bar = "█" * n + "░" * (len(group) - n)
            print(f"  {level:<7} {GREEN}{bar}{RESET} {n}/{len(group)}")

    print(f"\n{BOLD}{'ID':<22} {'SOLVED':<10} {'BEST':<8} {'IN TIME':<8} {'STARTS':>6} {'RESETS':>6} {'FAILED':>6}{RESET}")
    for s in scs:
        e = data.get(s.id)
        if not e:
            print(f"{DIM}{s.id:<22} {'-':<10} {'-':<8} {'-':<8} {0:>6} {0:>6} {0:>6}{RESET}")
            continue
        best = P.best_seconds(e)
        n_solves = len(e["solves"])
        in_time = any(x["within_limit"] for x in e["solves"])
        solved_s = f"{GREEN}{'✔ ' + ('x' + str(n_solves) if n_solves > 1 else ''):<10}{RESET}" if best is not None else f"{'-':<10}"
        print(f"{s.id:<22} {solved_s} {(_fmt_elapsed(best) if best is not None else '-'):<8} "
              f"{('yes' if in_time else ('no' if best is not None else '-')):<8} "
              f"{e['starts']:>6} {e['resets']:>6} {e['failed_checks']:>6}")

    recent = sorted(((x["at"], sid, x) for sid, e in data.items() for x in e["solves"]), reverse=True)[:5]
    if recent:
        print(f"\n{BOLD}Recent solves{RESET}")
        for at, sid, x in recent:
            print(f"  {time.strftime('%Y-%m-%d %H:%M', time.localtime(at))}  {sid:<22} {_fmt_elapsed(x['seconds'])}")


def cmd_stop(a) -> None:
    _scenario(a.scenario)
    vm.virsh("shutdown", C.domain_name(a.scenario), check=False)
    log("shutdown requested (state is kept; `ssh`/`check` will start it again)")


def _destroy(sid: str) -> None:
    disk, seed = _vols(sid)
    vm.dom_destroy(C.domain_name(sid))
    vm.vol_delete(disk)
    vm.vol_delete(seed)
    vm.clear_state(sid)


def cmd_destroy(a) -> None:
    ids = [s.id for s in S.all_scenarios() if vm.dom_exists(C.domain_name(s.id)) or vm.load_state(s.id)] if a.all else [a.scenario]
    for sid in ids:
        _scenario(sid)
        log(f"destroying {sid}")
        _destroy(sid)


def cmd_console(a) -> None:
    os.execvp("virsh", ["virsh", "-c", C.LIBVIRT_URI, "console", C.domain_name(a.scenario)])


# ---------------------------------------------------------------- argparse

def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="brokenbox", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor", help="check host prerequisites").set_defaults(fn=cmd_doctor)
    b = sub.add_parser("build-base", help="download Debian 12 and build the golden image")
    b.add_argument("--rebuild", action="store_true")
    b.set_defaults(fn=cmd_build_base)
    sub.add_parser("list", aliases=["ls"], help="list scenarios").set_defaults(fn=cmd_list)
    sub.add_parser("status", help="show running scenario VMs").set_defaults(fn=cmd_status)
    pr = sub.add_parser("progress", help="show which scenarios you've solved")
    pr.add_argument("--clear", action="store_true", help="erase all progress")
    pr.set_defaults(fn=cmd_progress)

    def scen(name, fn, help, **kw):
        sp = sub.add_parser(name, help=help, **kw)
        sp.add_argument("scenario")
        sp.set_defaults(fn=fn)
        return sp

    scen("describe", cmd_describe, "show a scenario's problem statement", aliases=["info"])
    for name, fn, help in [("start", cmd_start, "create the VM and break it"),
                           ("reset", cmd_reset, "revert the VM to its freshly-broken state")]:
        sp = scen(name, fn, help)
        sp.add_argument("--force", action="store_true", help="recreate if it already exists")
        sp.add_argument("--no-snapshot", action="store_true")
        sp.add_argument("-v", "--verbose", action="store_true", help="show setup output (spoilers!)")
    sp = scen("ssh", cmd_ssh, "ssh into the scenario VM as admin")
    sp.add_argument("--user", default="admin", choices=["admin", "root"])
    sp.add_argument("command", nargs=argparse.REMAINDER)
    scen("check", cmd_check, "run the solution checker")
    scen("stop", cmd_stop, "shut the VM down, keeping it")
    scen("console", cmd_console, "attach to the serial console")
    d = sub.add_parser("destroy", aliases=["rm"], help="delete a scenario VM")
    d.add_argument("scenario", nargs="?")
    d.add_argument("--all", action="store_true")
    d.set_defaults(fn=cmd_destroy)

    a = p.parse_args(argv)
    if a.cmd in ("destroy", "rm") and not a.all and not a.scenario:
        p.error("destroy needs a scenario or --all")
    try:
        a.fn(a)
    except Error as e:
        print(f"{RED}error:{RESET} {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
    except subprocess.TimeoutExpired as e:
        print(f"{RED}error:{RESET} timed out: {e.cmd}", file=sys.stderr)
        sys.exit(1)
