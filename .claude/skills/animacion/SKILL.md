---
name: animacion
description: Learn motion from a reference video and build animations for Agua GDL — UI transitions on the site (CSS) or short explainer videos (animated maps, collage, storyboard scenes). Use it when Ricardo sends a video or a post with one and says «aprende esta animación», «haz algo así», «anímalo», or asks for an animated map, a motion graphic, a transition or an explainer video.
---

Arguments: a reference (video file, or a post with one) and what to animate. Either may be missing.

A reference is a model for the form. The subject is always Guadalajara's water and Agua GDL's data (`.claude/rules/evidence.md`), in the shared look (`.claude/rules/vetos.md`: no off-brand styles).

## 0. The script, reviewed by Ricardo

Before anything else (studying a reference, a prompt, a still), write the script and have Ricardo review it (his rule, 25 Nov 2026). The script is every line that will be on screen or spoken, in order, each with its source and pin, and one sentence on what the picture does meanwhile. Nothing is built or handed off until he has approved it; a change to the wording afterwards goes back through him.

Review it on a page, not in chat (Ricardo, 25 Nov 2026). Copy `experiments/animacion/tlajomulco-amoniaco/guion.html` beside the film and change only its `VERSION`, `BEATS` (one row per line: time, text, source and pin, what the picture does) and `SUGS` (your suggestions or open questions, each with Sí / No / Sí, con cambios). Publish it with `capabilities: {comments: {}}`. Ricardo writes a note under each line and presses «Enviar a Claude», which sends every note as one comment to this session. «Copiar notas» gives the same text to paste in chat, for the other org or a local copy. Each round:
- read the thread, apply the notes, bump `VERSION`, and publish to the same URL with `edits`;
- mark every changed line «cambio vN» in its source field, and keep facts you could not check marked «sin verificar»;
- when a note conflicts with `evidence.md` or a rule in this skill, ask on the page as a question rather than applying it silently, and write his answer into the rule;
- resolve the thread once applied;
- end with an approval question; approval is a «Sí» there or his word in chat.

## 1. Study the reference

Never describe motion from the post's text or from memory: measure it.

1. Get the video. For an X post, `https://api.fxtwitter.com/<user>/status/<id>` returns the full text, the quoted post and each video's variants; take the 720 px one. Ask Ricardo before downloading (file, source, size) and save it in its own empty folder outside the repo.
2. Build the frame tool (macOS only; no ffmpeg needed):
   `swiftc -O -o <tmp>/frames .claude/skills/animacion/frames.swift`
3. Overview: `<tmp>/frames <video> <outdir> 240 6 5` prints duration, fps and size, writes `motion.csv` (per frame: mean luma change against the previous frame) and one contact sheet of 30 timestamped frames.
4. Find the transitions in `motion.csv`: a run of frames above ~0.3 is one move and runs of 0 are holds. One isolated spike is a hard cut; a run of high values is a fast camera move, not a cut. Count frames; milliseconds = frames × 1000 / fps. The spans include the fades between scenes, so take where a move starts and settles from the dense sheet. Motion mostly on every other frame means it is animated on twos.
5. Dense sheet per transition, one cell per frame: `<tmp>/frames <video> <outdir> 300 6 4 <t0> <t1> <1/fps>`. Read the sheet. When several scenes play side by side, study one at a time with `CROP=x,y,w,h` (fractions of the frame, from the top left) in front of the command.
6. Write one row per transition: trigger, duration (frames and ms), what changes (position, size, opacity, blur, colour, radius), order and stagger, what holds still, how it ends (overshoot, settle). Mark each value «measured» (from the csv) or «by eye» (from a sheet). Easing is always by eye.

`referencias.md` holds the rows from the references studied so far. Add to it; don't re-measure what is there.

## 2. Build

Don't build the animation in the session that planned it. Write a prompt for another agent to build it in a fresh session, and give Ricardo that prompt (Ricardo's rule, 25 Nov 2026; a long session re-reads itself on every call, about 240k tokens each by the end of the first film). The prompt stands alone:
- the goal and where the piece will be shown (format, size, length, with or without voice);
- the script and the list of beats with timings;
- every fact on screen with its source file and pin, and the quotes as written;
- the data files to read and the numbers the build must assert;
- «use the `animacion` skill» and the rules that bind it (`evidence.md`, `vetos.md`, the No cuadra skill if it is one);
- where the files and the video go, and what to report back (checked, not checked, nothing committed).

The beats and timings are set on the script Ricardo approved in step 0; show him that list too before writing the prompt for anything long.

**On the site (`web/`)**: read `.claude/rules/web.md` first.
- CSS transitions and `@keyframes` on `transform` and `opacity` only; no animation library.
- Reuse the durations and curves already in `web/reportes.html` (grep `cubic-bezier` and `transition:`) before adding new ones.
- Everything sits inside `@media (prefers-reduced-motion: no-preference)` or has a `reduce` override, and the page reads the same with motion off. Ricardo's iPhone has Reduce Motion on: he won't see it there.
- Motion explains a change of state (where a panel came from, which row opened). Nothing loops, nothing moves while the visitor reads.
- Check with `npm run dev` and `node scripts/shot.mjs <path>` at both widths.

**As a video** (outside `web/`; working files in `experiments/` or the notes repo):
- Script first: one short sentence per beat, every date, number and place tied to its source. No real person's likeness. Logos only of the public bodies the film names (SIAPA, municipios), from their official sites or Ricardo's files (Ricardo, 25 Nov 2026); no other logos.
- Geography from the repo's data (`web/zones.json`, `web/colonias_siapa.topo.json`), never drawn by hand.
- Write the timing first: one list of beats with frame numbers, from the voice-over's words, and read every cue from it. Give every element an end frame.
- Every frame is a function of its frame number alone (no clocks, no random without a seed, no state carried over), so any frame can be drawn by itself and checked.
- Write numbers, not adjectives: durations in frames, colours in hex, curves as `cubic-bezier`, bounce as a damping ratio (1.0 none, for text; 0.8 one small bounce; 0.5 two, for characters). Exits run shorter than entrances.
- Draw frames in code at 30 fps and encode them; say what had to be installed (ffmpeg is not on this Mac).
- Render a contact sheet of 10–12 frames and fix overlaps, empty stretches and text off-frame before the full render.
- Ricardo publishes; this skill only produces the file.

## 3. Check your own output

Stills can't show motion: a frozen video passes a check made of screenshots.

- **Video:** run the frame tool on the rendered file. Every planned move shows as a bump in `motion.csv`; a hold of 0.5 s or more that the beat list doesn't ask for is a bug; in a loop, the last frame flows into the first. Then compare its rows with the reference's: durations within a frame or two, same order, same holds.
- **CSS:** the durations are the ones written in the stylesheet; what needs checking is each state on the way. On a copy of the page, trigger the change and freeze it: `for (const a of document.getAnimations()) { a.pause(); a.currentTime = ms }`, with `ms` from the URL, then screenshot each time with headless Chrome (`--headless=new --screenshot`). Check the start, a third, two thirds and the end, at 390 and 1300 px.
- Report each check with its number, and what was not checked. Ricardo presses play before anything is published.

When a reference teaches something new, or a check finds a miss, add it to `referencias.md` or to this file.

## 4. Render a video without installs

Used for `experiments/animacion/tlajomulco-amoniaco/` (25 Nov 2026): no ffmpeg, only Chrome and Swift.

- One HTML file with a fixed stage (1080×1920 vertical) and `window.renderAt(t)`, a pure function of time that sets every style; the page reads `?f=<frame>` and calls `renderAt(f / FPS)`. No CSS transitions, timers or `Date`.
- A `build.py` beside the template fills in the data from the repo and asserts every number the film states (max, dates, ratios), so a data change fails the build instead of leaving a wrong figure on screen.
- Stills first: shoot five or six frames (`shoot.sh <film.html> <outdir> <frame>`) and look at them for overlaps before the full run. Stack blocks by measured height, not by guessed `top` values.
- Full run: one `shoot.sh` per frame, 8 in parallel (`seq 0 N | xargs -P 8 -I{} sh shoot.sh …`). About 1,100 frames took 6–7 minutes. A Chrome can hang on a frame: count the PNGs, kill the stuck process and re-shoot the missing ones.
- Encode: `swiftc -O -o <tmp>/encode encode.swift`, then `encode <framesDir> <out.mp4> 30` (H.264, no audio). Finished videos go in `~/Movies/agua-gdl/`, never in `web/`.
- Then step 3 on the encoded file: every planned beat shows a bump in `motion.csv` and holds fall only where the viewer reads.
