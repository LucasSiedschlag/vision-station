# Operator guide: Vision Station

One page. The screen shows whether the part is good and, if it is not, why.

## The screen

```
┌──────────────────────────────────────────────────────────────┐
│ Job name  v7                                        Log in   │
│                                    │      ✔                  │
│        CAMERA IMAGE                │     PASS                │
│                                    │   reason, when it fails │
│                                    │ Last: ✔ ✔ ✘ ✔           │
│                                    │ Today: total · ✔ · ✘ · !│
│                                    │ [Inspect now]           │
│ ● System  ● Camera  ● Recording            Waiting for part  │
└──────────────────────────────────────────────────────────────┘
```

## What each result means

| On screen | Color | What to do |
|---|---|---|
| **Waiting for a part** | grey | Put the part in place and keep it still. The photo is taken automatically |
| **Inspecting…** | blue | Do not touch the part |
| **PASS** | green | Go ahead |
| **FAIL** + reason | red | Fix what the reason says (e.g. "Cap missing") and place the part again. It is inspected again |
| **ERROR** + reason | yellow | The system **could not** check the part (dark image, part out of position, camera). **It is not a pass.** Adjust and try again; if it repeats, call maintenance |
| **Camera disconnected** | yellow | Call maintenance. Nothing is passed while this shows |

The word (PASS, FAIL, ERROR) always comes together with the color.

## Buttons

- **Inspect now:** takes the photo right away, without waiting for the part to be still. It only works while the screen says *Waiting for a part*.
- **Incorrect result?:** if the system got it wrong (said FAIL for a good part, or the other way round), tap here and say what the right answer was. The image is kept to improve the system. It does not change what already happened.
- **Log in:** only for the Supervisor and the Maintainer.

## The dots at the bottom

- **System**, **Camera**, **Recording**: green means all is well. Yellow or red: tell maintenance.
- **Today:** how many parts, passes, fails and errors since the start of the shift.
