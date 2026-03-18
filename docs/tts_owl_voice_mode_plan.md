# TTS + Ms. Olivia Voice Mode — Implementation Plan

## Goal

Add Cartesia Sonic TTS to the voice pipeline. When TTS is toggled on, replace the **chat message area only** (the scrollable middle section) with a centered, animated Lottie owl — **Ms. Olivia**. The header, ChatInput, ReferencePanel, and security code button all remain visible and functional. The owl animates between listening and speaking states. A speech rate toggle lets users control TTS speed.

## Character Rename: Ollie → Ms. Olivia

All references to "Ollie" throughout the codebase are renamed to **"Ms. Olivia"**:
- Backend system prompt (`backend/app/services/llm.py`)
- Frontend chat labels (`ChatMessage.tsx`, `App.tsx` loading indicator)
- Header brand text if applicable
- Test fixtures and assertions

## Owl Asset: Lottie Animation

**Selected**: "Smiling Owl" — free Lottie animation from LottieFiles
- Format: Lottie JSON, 1000×1000px, 60fps, 125 frames
- File location: `frontend/src/animations/olivia-owl.json` (**DONE** — already downloaded)
- Features: blinking eyes, smiling/opening beak, wing flaps, gentle body bounce
- Package: `lottie-react` (npm) for rendering in React

**Animation state control via `lottie-react`**:
- The Lottie `<Player>` component exposes `speed`, `direction`, and play/pause controls
- **Listening** (user speaking): normal speed (1×), gentle idle/blink — the default animation
- **Speaking** (TTS playing): faster speed (1.5–2×) + subtle CSS scale pulse — feels more animated/active, like Ms. Olivia is talking
- **Processing** (waiting for LLM): slow speed (0.5×) — contemplative pause
- **Idle**: paused on a single frame or very slow (0.3×)

---

## Current Layout (Text Mode)

```
┌──────────────────────────────────────────────────────────────┐
│  Header  [🦉 Sunshine Learning Center]       [🎙️ Voice]    │
├──────────────────────────────────┬───────────────────────────┤
│                                  │                           │
│  ┌────────────────────────┐      │  References               │
│  │ Ms. Olivia: Hi! How    │      │  • Illness Policy (p.43)  │
│  │ can I help you today?  │      │  • Hours (p.31)           │
│  └────────────────────────┘      │                           │
│                                  │  Child: Sofia Martinez    │
│  ┌────────────────────────┐      │                           │
│  │ You: What time do you  │      │                           │
│  │ open?                  │      │                           │
│  └────────────────────────┘      │                           │
│                                  │                           │
│  ← THIS AREA gets replaced →    │  ← STAYS                  │
│                                  │                           │
├──────────────────────────────────┴───────────────────────────┤
│  [Type a message...]                              [Send]     │  ← STAYS
│  Have a security code? Enter it to access child info         │  ← STAYS
└──────────────────────────────────────────────────────────────┘
```

## TTS-On Layout (Ms. Olivia Voice Mode)

```
┌──────────────────────────────────────────────────────────────┐
│  Header  [🦉 Sunshine Learning Center]                      │
│  [🎙️ Voice] [🔊 TTS On] [⏩ 1.0×]                         │
├──────────────────────────────────┬───────────────────────────┤
│                                  │                           │
│                                  │  References               │
│       ┌────────────────┐         │  • Illness Policy (p.43)  │
│       │                │         │  • Hours (p.31)           │
│       │  [Lottie Owl]  │         │                           │
│       │  Ms. Olivia    │         │  Child: Sofia Martinez    │
│       │  (animated)    │         │                           │
│       └────────────────┘         │                           │
│                                  │                           │
│       ● Listening...             │                           │
│       "what time does the..."    │                           │
│       (interim transcript)       │                           │
│                                  │                           │
│  ← ONLY this area changes →     │  ← STAYS                  │
│                                  │                           │
├──────────────────────────────────┴───────────────────────────┤
│  [Type a message...]                              [Send]     │  ← STAYS
│  Have a security code? Enter it to access child info         │  ← STAYS
└──────────────────────────────────────────────────────────────┘
```

**Key point**: Only the `<div className="flex-1 overflow-y-auto p-4">` area in App.tsx (lines 109–134) is swapped. Header, ChatInput, ReferencePanel, voice status, and security code button are untouched.

---

## Implementation Steps

### Step 1: Backend — Cartesia TTS Service (TDD)

**Tests first** → `backend/tests/test_tts.py`:
- `strip_markdown` removes bold/italic/headers/links/code blocks
- `split_into_sentences` handles `.!?` boundaries and abbreviations (Dr., Mrs., etc.)
- `synthesize()` with mocked Cartesia client returns audio bytes
- `synthesize()` passes `speed` parameter to Cartesia
- `read_response_chunked()` sends N `tts_audio_chunk` events + 1 `tts_complete`
- Graceful no-op when API key is empty (returns no audio, no error)

**New file** → `backend/app/services/cartesia_tts.py`:
- `CartesiaTTSService` class:
  - Constructor receives API key + voice ID (injected, not global)
  - `synthesize(text: str, speed: float = 1.0) -> bytes` — calls `cartesia.AsyncCartesia` REST `tts.bytes()` endpoint
  - Returns raw PCM16 24kHz audio bytes
- `strip_markdown(text: str) -> str` — free function, removes `**bold**`, `*italic*`, `# headers`, `[links](url)`, `` `code` ``
- `split_into_sentences(text: str) -> list[str]` — free function, splits on `.!?` while respecting abbreviations
- `TTSResponseReader` class:
  - Constructor receives `CartesiaTTSService` + `WebSocket`
  - `read_response_chunked(text: str, speed: float = 1.0)` — strips markdown → splits sentences → synthesizes each → sends base64-encoded PCM16 chunks as `{"type": "tts_audio_chunk", "audio": "<base64>"}` → sends `{"type": "tts_complete"}`

**Modify** → `pyproject.toml`: add `cartesia>=1.0.0` dependency
**Modify** → `backend/app/main.py`: create `CartesiaTTSService` in lifespan, store in `app.state.tts_service` (None if no API key)

### Step 2: Backend — WebSocket TTS Integration + Speed (TDD)

**Tests first** → extend `backend/tests/test_voice_websocket.py`:
- Config message with `tts_enabled: true` acknowledged correctly
- Config message with `tts_speed: 1.25` stored in session state
- Default `tts_enabled: false` when field not specified (backward compat)
- Default `tts_speed: 1.0` when field not specified
- Audio chunks sent after text response when TTS enabled
- No audio chunks when TTS disabled — text response still delivered
- TTS error doesn't break text response delivery (try/except isolation)
- Speed parameter forwarded to `TTSResponseReader`

**Modify** → `backend/app/api/websocket.py`:
- Extract `tts_enabled` (bool) and `tts_speed` (float) from config message
- In `process_utterance()`, after sending text response JSON:
  - If `tts_enabled` and `app.state.tts_service` is not None:
    - Send `{"type": "tts_start"}` (signals frontend to mute mic)
    - Call `TTSResponseReader.read_response_chunked(text, speed=tts_speed)`
    - `tts_complete` is sent by the reader (signals frontend to unmute mic)
  - Wrap entire TTS block in try/except — TTS failure logged, never blocks text

### Step 3: Frontend — `useTTS` Hook (TDD)

**Tests first** → `frontend/src/hooks/__tests__/useTTS.test.ts`:
- Starts in `idle` state
- Transitions to `playing` when `handleChunk()` called with audio data
- Returns to `idle` when `handleComplete()` called
- `stop()` clears playback queue and resets state to `idle`
- Multiple chunks queued play gaplessly (no gaps between sentences)

**New file** → `frontend/src/hooks/useTTS.ts`:
```ts
interface UseTTSReturn {
  state: 'idle' | 'playing'
  handleChunk: (base64Audio: string) => void
  handleComplete: () => void
  stop: () => void
}
```
- `AudioContext` at 24kHz sample rate
- `handleChunk()`: decode base64 string → `Int16Array` → `Float32Array` (normalize to -1..1) → create `AudioBuffer` → schedule with `AudioBufferSourceNode`
- Gapless playback: track `nextStartTime`, schedule each chunk to begin when previous ends
- `handleComplete()`: mark that no more chunks coming, transition to `idle` when last buffer finishes
- `stop()`: disconnect all nodes, reset queue, set state `idle`

**Modify** → `frontend/src/types/api.ts`:
- Add to `ServerEvent` union:
  - `{ type: 'tts_start' }`
  - `{ type: 'tts_audio_chunk', audio: string }` (base64 PCM16)
  - `{ type: 'tts_complete' }`

**Modify** → `frontend/src/hooks/useVoice.ts`:
- New props: `ttsEnabled: boolean`, `ttsSpeed: number`
- Send `tts_enabled` and `tts_speed` in WebSocket config message
- New internal `useTTS()` instance
- Handle incoming WebSocket messages:
  - `tts_start` → mute mic (stop sending audio frames to prevent echo)
  - `tts_audio_chunk` → forward `data.audio` to `tts.handleChunk()`
  - `tts_complete` → call `tts.handleComplete()`, unmute mic
- Expose `ttsState` from hook return value

### Step 4: Frontend — `OliviaVoiceView` Component (TDD)

**Tests first** → `frontend/src/components/__tests__/OliviaVoiceView.test.tsx`:
- Renders the Lottie owl animation
- Shows "Ms. Olivia" label
- Shows "Listening..." label when `voiceState === 'listening'`
- Shows "Speaking..." label when `ttsState === 'playing'`
- Shows "Processing..." label when `voiceState === 'processing'`
- Displays interim transcript text when provided
- Hides interim transcript when empty string
- Lottie speed prop changes per state (mock `lottie-react`)

**New file** → `frontend/src/components/OliviaVoiceView.tsx`:

```tsx
import Lottie from 'lottie-react'
import oliviaOwl from '@/animations/olivia-owl.json'

interface OliviaVoiceViewProps {
  voiceState: 'idle' | 'connecting' | 'listening' | 'processing'
  ttsState: 'idle' | 'playing'
  interimText: string
}
```

- Centered flex container: `flex-1 flex items-center justify-center flex-col`
- Lottie owl rendered at ~250×250px, centered
- **Lottie animation speed controlled by state**:
  - `ttsState === 'playing'` → speed `1.8`, loop — active/talking feel
  - `voiceState === 'listening'` → speed `1.0`, loop — natural idle/blink
  - `voiceState === 'processing'` → speed `0.5`, loop — slow contemplation
  - `idle` → speed `0.3`, loop — very gentle breathing
- **Subtle CSS ring behind the owl** (optional accent, not primary indicator):
  - Speaking: blurple glow (`shadow-blurple/40`)
  - Listening: soft red glow (`shadow-bw-red/30`)
  - Processing: orange glow (`shadow-bw-orange/30`)
  - Idle: none
- State label below: "Ms. Olivia" + state text ("Listening...", "Speaking...", etc.)
- Interim transcript: small faded text (`text-blueberry/50 italic`) below state label

**Display state priority logic:**
1. `ttsState === 'playing'` → **Speaking** (TTS takes priority over everything)
2. `voiceState === 'listening'` → **Listening**
3. `voiceState === 'processing'` → **Processing**
4. Otherwise → **Idle**

### Step 5: Frontend — TTS Toggle + Speed Toggle in Header (TDD)

**Tests first** → extend `frontend/src/components/__tests__/Header.test.tsx`:
- TTS toggle button visible when `voiceEnabled` is true
- TTS toggle button hidden when `voiceEnabled` is false
- Click TTS toggle calls `onToggleTTS`
- Speed button visible when `voiceEnabled && ttsEnabled`
- Speed button hidden otherwise
- Speed button displays current speed text (e.g., "1.0×")
- Click speed button calls `onCycleSpeed`

**Modify** → `frontend/src/components/Header.tsx`:
- New props: `ttsEnabled?: boolean`, `onToggleTTS?: () => void`, `ttsSpeed?: number`, `onCycleSpeed?: () => void`
- When `voiceEnabled`: render TTS toggle button (🔊 On / 🔇 Off)
- When `voiceEnabled && ttsEnabled`: render speed button (⏩ 1.0×)
- Speed presets: `[0.8, 1.0, 1.25, 1.5]` — button label shows current, click cycles to next
- Styling consistent with existing voice toggle (rounded-full pills)

### Step 6: Frontend — App.tsx Layout Integration

**Modify** → `frontend/src/App.tsx`:
- Import `OliviaVoiceView` and `lottie-react`
- Add state: `ttsEnabled` (default `false`)
- Add state: `ttsSpeed` (default `1.0`)
- `handleToggleVoice()`: when enabling voice, also set `ttsEnabled = true`; when disabling, set `ttsEnabled = false`
- `handleToggleTTS()`: toggle `ttsEnabled`
- `handleCycleSpeed()`: cycle through `[0.8, 1.0, 1.25, 1.5]`
- Pass `ttsEnabled` and `ttsSpeed` to `useVoice`
- Pass `ttsEnabled`, `onToggleTTS`, `ttsSpeed`, `onCycleSpeed` to `Header`
- **Conditional rendering in messages area only** (replaces lines 109–134):
  ```tsx
  {voiceEnabled && ttsEnabled ? (
    <OliviaVoiceView
      voiceState={voice.state}
      ttsState={voice.ttsState}
      interimText={voice.interimText}
    />
  ) : (
    <div className="flex-1 overflow-y-auto p-4">
      {messages.map((msg) => (
        <ChatMessage key={msg.id} message={msg} />
      ))}
      {/* loading indicator, error, messagesEndRef */}
    </div>
  )}
  ```
- Voice status bar, security code button, ChatInput, ReferencePanel — all unchanged
- ChatInput remains functional in owl mode (user can still type)

### Step 7: Rename Ollie → Ms. Olivia

**Backend changes:**
- `backend/app/services/llm.py`: update system prompt — "You are Ms. Olivia, the friendly AI Front Desk assistant..."
- `backend/tests/`: update any test assertions referencing "Ollie"

**Frontend changes:**
- `frontend/src/App.tsx`: loading indicator label "Ollie" → "Ms. Olivia" (line 116)
- `frontend/src/components/ChatMessage.tsx`: assistant name label "Ollie" → "Ms. Olivia" (if present)
- `frontend/src/components/__tests__/`: update test assertions

### Step 8: Styling + Animation Polish

- Lottie container: slight `drop-shadow` for depth, no hard border
- Smooth transition between glow colors: `transition-shadow duration-500`
- Responsive: Lottie scales down on mobile (`w-48 md:w-64`) but stays centered
- Interim transcript: `animate-pulse` for subtle "live" feel, truncate if too long
- Speed button: highlight current speed with `bg-blurple text-white` when not at 1.0×
- Install `lottie-react`: `npm install lottie-react`

---

## Files Summary

### New Files
| File | Purpose |
|------|---------|
| `backend/app/services/cartesia_tts.py` | Cartesia TTS service, markdown stripping, sentence splitting |
| `backend/tests/test_tts.py` | TTS service unit tests |
| `frontend/src/animations/olivia-owl.json` | Lottie animation file (DONE — already downloaded) |
| `frontend/src/hooks/useTTS.ts` | Audio playback hook (decode + queue + gapless play) |
| `frontend/src/hooks/__tests__/useTTS.test.ts` | useTTS tests |
| `frontend/src/components/OliviaVoiceView.tsx` | Centered Lottie owl with state-driven animation |
| `frontend/src/components/__tests__/OliviaVoiceView.test.tsx` | OliviaVoiceView tests |

### Modified Files
| File | Change |
|------|--------|
| `pyproject.toml` | Add `cartesia>=1.0.0` |
| `backend/app/main.py` | Create TTS service in lifespan → `app.state.tts_service` |
| `backend/app/api/websocket.py` | TTS integration, tts_enabled/tts_speed config, mute signaling |
| `backend/app/services/llm.py` | Rename Ollie → Ms. Olivia in system prompt |
| `backend/tests/test_voice_websocket.py` | TTS WebSocket tests |
| `frontend/package.json` | Add `lottie-react` dependency |
| `frontend/src/types/api.ts` | Add TTS event types to ServerEvent union |
| `frontend/src/hooks/useVoice.ts` | Accept ttsEnabled/ttsSpeed, handle TTS events, mic muting, expose ttsState |
| `frontend/src/components/Header.tsx` | TTS toggle + speed toggle buttons |
| `frontend/src/components/__tests__/Header.test.tsx` | Tests for TTS/speed toggles |
| `frontend/src/App.tsx` | ttsEnabled/ttsSpeed state, conditional OliviaVoiceView in messages area, rename labels |
| `frontend/src/components/ChatMessage.tsx` | Rename Ollie → Ms. Olivia |
| `frontend/src/index.css` | Optional: custom glow animation keyframes |

### No Backend Schema Changes
TTS is a runtime feature — no database changes required.

---

## Progress Tracking

- [ ] Step 1: Backend — Cartesia TTS Service (tests + implementation)
- [ ] Step 2: Backend — WebSocket TTS integration + speed (tests + implementation)
- [ ] Step 3: Frontend — useTTS hook (tests + implementation)
- [ ] Step 4: Frontend — OliviaVoiceView component with Lottie (tests + implementation)
- [ ] Step 5: Frontend — Header TTS toggle + speed toggle (tests + implementation)
- [ ] Step 6: Frontend — App.tsx layout integration
- [ ] Step 7: Rename Ollie → Ms. Olivia across codebase
- [ ] Step 8: Styling + animation polish
