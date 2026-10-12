# ctr360 — continuation prompt for a fresh session

Copy everything below the line into a new chat/session.

---

Continue work on the **ctr360** project: a source port of Crash Team Racing (PSX) to
native Xbox 360, with the goal of booting through the menu to the **title screen**
and then into gameplay, with framebuffer output matching the PSX reference.

**Read first, in full:**
`F:\downloads\temp\python\hermes\ctrport\ctr360\HANDOFF.md` (state, paths, commands,
probe rules, cooker rules) — then:
1. `IMPLEMENTATION_PLAN.md` — the independent audit's plan and its §12 checklist;
   work from it (HANDOFF §1 has the checklist status, §2 the ordered work).
2. `research/session9_trace_and_frame_pos.md` — session 9 (the infra, the
   ModelFrame.pos cook bug, the two stall modes, the empty 3D emission).
3. `research/visual_gate_plan.md` — the session-7b plan and the convention table.
4. `research/gte_endianness_findings.md` — the byte-order bug class (sessions 6-8).

**Where things stand (one paragraph):** the guest runs end-to-end to the title
(f=734, title camera sweeps and settles, zero `[fault]`) and the packet ABI is
nearly clean (session 8: `invalid tag length` 99 -> 1, prim overshoots 354 -> 4).
Session 9 finished the plan's infra items — trace categories + buffered logging
(quiet run log: 634 lines instead of 3.9 MB) and the reproducible run harness
(`tools/ctr360/run_harness.py`: minimized launch, `--until-frame` early stop,
per-capture decoded pixelsums) — and fixed the first Phase-2 divergence:
`ModelFrame.pos` was cooked as one reversed block, which rotated x/y/z by a
halfword for every reader (now per-u16; `cooked == byteswap16(retail)` for all 18
ModelAnim candidates of entry 514, and the guest's projection values are sane:
`pj f=61 sxy=0061ffcd sz=1133` vs the old `sxy=03ff0100 sz=0`). **Pixels are
still the gate, and they say nothing draws**: every scheduled VRAM capture from
f=12 to f=205 has the identical pixelsum `6811c482ead27c0b` (the copyright page).
Two facts localize why: (a) most runs never reach a 3D frame — the guest stalls
either **parked** right after `[trace] pi done` (`MainInit_JitPoolsNew`'s tail;
`stage=1` never prints; prime suspect is stage 1's XA fade wait, and XA assets are
not staged) or **spinning** at f=21 just after the `[trace] g0` marker in
`MainFrame`'s game-logic section; and (b) in the runs that do reach the crate
frames (f=13-61), instances queue (22/frame) and `RenderBucket_DrawFunc_Normal`
runs (4/frame) yet `DrawAllSplits: 0 split(s) at 0 verts` and the OT holds only
the 2D present/pack quads — the draw path emits no 3D prims at all.

**Immediate task (HANDOFF section 2, in order):**
1. Get one run into a 3D frame and judge the pixels — the acceptance signal for
   the pos fix: `python tools/ctr360/run_harness.py --secs 75 --until-frame 61
   --trace "boot,cull,title,vram,misc,packet" --tag pix --expect-frame 61`, then
   compare `ctr360_crate61_f0061_vram.tga`'s pixelsum against
   `6811c482ead27c0b`. Every Phase-2 step's acceptance is a pixelsum that differs.
2. Fix the two boot/load stalls (both upstream of any 3D frame): the parked one
   after `pi done` (stage 0 -> 1; the XA fade wait) and the spinning one at f=21
   after `g0` (the `g1m..g7m` sub-phase probes are menu-gated, so widen them to
   cover cutscene frames).
3. Explain the empty 3D emission — the new `dw` probe (PACKET) prints each
   `DrawFunc_Normal` call's command-list count and first words, which says
   whether the command list is empty or the strip/prim emission bails.
4. The residual packet anomaly (`db0/db1.prim+0x220`, ~5 reports/run).
5. Frame time (0.7-2.3 s/frame; the platform sub-timings are small, so it is in
   game/native_gpu — prime suspect: the VRAM upload path's per-rect locks).
6. Then Phases 3-5 (stable title, demo race, hardware validation).

**Operating rules (user-granted):** work autonomously — launch and kill Xenia
yourself, judge from guest logs. The user is the visual judge: report a milestone
only when pixels changed (framebuffer dump or the user's check), never from state
alone. **Keep runs short — stop at the target frame (`--until-frame`) instead of
burning minutes; the freeze is early (f=0-25).** Xenia launches minimized so it
does not steal focus. Keep the real-console path viable; Xenia config options only
for debugging. Trust `build_xex.sh`'s FATAL gates. Stage with
`bash tools/ctr360/prep_test.sh --cooked build-360/ctr-u-360.bin` and md5-assert
the staged asset. Probe-insertion rules are in HANDOFF section 5 — never insert a
probe between an `if (...)` header and its `{`; never write probes via shell
heredocs; `check_probes.py` before every build. Apply edits to both the repo tree
and `build-360/gen` (the tree is what runs).

---
