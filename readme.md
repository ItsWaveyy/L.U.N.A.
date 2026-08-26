# L.U.N.A.

### Lowkey Useful (or Useless) Neural Assistant

L.U.N.A. is a modular, voice-first personal AI assistant designed to be
independent of any single AI provider.

The goal is simple:

> Build an AI assistant that belongs to the user, rather than an assistant
> locked to one company, model, or device.

---

## Current Status

**Version:** v0.05.4.4
**Development:** Active

L.U.N.A. currently has a working realtime voice interface powered by
Kokoro alongside an experimental provider architecture
designed to support multiple AI brains and automatic fallback.

---

## Architecture

L.U.N.A. is being built as a layered system rather than a single AI model.

```text
                         L.U.N.A. CORE
                              │
              ┌───────────────┼───────────────┐
              │               │               │
           MEMORY           ROUTER           TOOLS
              │               │               │
              │        ┌──────┼──────┐        │
              │        ↓      ↓      ↓        │
              │      Gemini  Local  OpenAI     │
              │               │               │
              └───────────────┴───────────────┘
                              │
                              ↓
                         Voice Layer
                              │
                           LiveKit


                           🎤 MIC
                              │
                              ▼
                              ┌──────────────────────┐
                              │ SPEAKER IDENTITY GATE│
                              │                      │
                              │  WHO THE FUCK IS THIS│
                              └──────────┬───────────┘
                                       │
                                    ┌────┴─────┐
                                    │          │
                                 DENIED      ALLOWED
                                    │          │
                                 DROP     RELEASE
                                             │
                                             ▼
                                       ai-coustics
                                             │
                                             ▼
                                          Silero
                                             │
                                             ▼
                                             Groq
                                             │
                                             ▼
                                             LUNA


                                             

                           L.U.N.A. v0.05

         Smart routing             ████████████████████  DONE
         Offline Core              ████████████████████  DONE
         Voice intelligence        █████████████████░░░  ~90%
         Speaker identity          █████████████░░░░░░░  ~65%
         Core → Agent integration  ████░░░░░░░░░░░░░░░░  NOT DONE
         Full offline operation    ██░░░░░░░░░░░░░░░░░░  NOT DONE
         Full online operation     █████████████░░░░░░░  PARTIAL
         Failure/recovery          ██░░░░░░░░░░░░░░░░░░  NOT DONE