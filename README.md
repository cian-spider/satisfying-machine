# satisfying-machine

A 12 second, 1080p, seamlessly looping machine animation, generated entirely by
`render.py`. No 3D software, no video editor, no stock assets. One Python file,
the Python standard library, and Pillow.

**Output:** `machine.mp4` - 1920x1080, 30 fps, 360 frames, 12.00 s, H.264.

## How the loop is seamless

This is the design decision the whole thing rests on.

Every animated quantity is a **pure function of the loop phase** `p = frame / frames`,
and every motion term uses only **integer harmonics** of that phase
(`sin(2*pi*k*p)` for integer `k`). There is no integration, no state carried
between frames, and no easing at the ends. Therefore the state at frame `N` is
identical to the state at frame `0` by construction, not by tuning.

That has a consequence worth stating: the video can be cut at *any* frame and
still loop, because there is no privileged start point. Frame 359 differs from
frame 0 only by one frame of normal motion.

Verified mechanically, not by eye:

```
ffmpeg -i machine.mp4 -vf "select='eq(n\,0)+eq(n\,359)',scale=64:36" \
  -vsync 0 -f rawvideo -pix_fmt gray - | ...
# mean absolute difference between first and last frame: 0.50 / 255
```

## The machine

Seven assemblies, each driven by the same phase, so they interlock instead of
merely coexisting:

1. **Main gear** - one full revolution per loop. All other timing is derived from it.
2. **Two counter-rotating gears** - meshed at exact integer tooth ratios, so their
   teeth never intersect at any frame.
3. **Crank pin, connecting rod, horizontal piston** - the pin rides the main gear
   and drives the rod. Piston travel is the projection of the pin position.
4. **Cam and hammer** - the cam sits on the second gear and lifts the hammer, which
   drops onto the piston's forward stroke.
5. **Serpentine ramp with six balls** - one ball released per tooth pass. Ball
   position along the ramp is a closed-form function of phase, not a simulation.
6. **Conveyor with six cups** - carries each landed ball back to the top of the
   ramp, closing the material loop as well as the visual one.
7. **Frame and shadow plate** - static, provides depth.

The material loop matters as much as the visual one: balls that leave the ramp
come back to it, so a viewer cannot find a discontinuity even if they look for one.

## Render it yourself

Requirements: Python 3.12 and Pillow, plus an `ffmpeg` binary. The script looks
for `~/.local/ffmpeg/ffmpeg` by default; override with `--ffmpeg /path/to/ffmpeg`.

```bash
pip install pillow
python3 render.py machine.mp4 --frames 360 --fps 30 --scale 1
```

`--scale 2` renders at 3840x2160. Frames are written as PNG to a temporary
directory and encoded with `libx264 -preset slow -crf 17 -pix_fmt yuv420p
-movflags +faststart`, so the result plays anywhere and starts without a seek.

Measured on 2 vCPU: about 60 s for 360 frames at 1080p.

## Files

| File | What it is |
|---|---|
| `render.py` | The whole animation. Geometry, palette, timing, encoder call. |
| `machine.mp4` | The rendered result. |
| `README.md` | This file. |

## Licence

MIT. Use it, fork it, cut it at a different frame.
