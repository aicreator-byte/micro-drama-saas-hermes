# Fix Round 2 Progress

## Error Categories Identified

### (a) Select API Mismatch
- `placeholder` prop not on `SelectRootProps` (multiple pages)
- Missing `SelectItem`, `SelectTrigger`, `SelectValue`, `SelectContent` components
- Missing `Textarea`, `Input` components

### (b) api.ts - Missing Type Imports
- Cannot find: Project, SeriesBible, Character, PaginatedResponse, Episode, Scene, SceneCharacter, Dialogue, Prompt, PromptGenerationRequest, PromptGenerationResponse, GoogleAccount, FlowTask, AssetType, Asset, StoryGenerationRequest, StoryGenerationResponse, SceneBreakdownRequest, SceneBreakdownResponse

### (c) project-store.ts - Location Type Conflicts
- Location type mismatch (missing id, project_id, name, description, etc.)
- Partial<Location> type conflicts
- Array type mismatches

### (d) Other Page-Level Type Errors
- assets/page.tsx: Record<"image", ...> missing "video", "document" keys
- dialogues/page.tsx: missing selectedScene/setSelectedScene, wrong arg counts, Dialogue[] vs number comparison
- episodes/page.tsx: number/string mismatches
- flow/page.tsx: video_generation vs image_generation, fontMono prop on Textarea
- page.tsx: missing fetchProjects, projects
- projects/page.tsx: missing total_pages, projects, fetchProjects
- series-bible/page.tsx: subplots string vs Record<string, unknown>[]
- prompts/page.tsx: fontMono prop on Textarea

---

## Progress Log

### Step 1: Fix Select Component (Group a) ✓
- Target: `src/components/ui/Select.tsx`
- Added `placeholder` prop to `SelectRootProps`
- Created separate `Input.tsx` and `Textarea.tsx` components with `fontMono` support
- Files using Select: assets/page.tsx, dialogues/page.tsx, flow/page.tsx, projects/page.tsx, prompts/page.tsx
- **Build errors after: ~120** (down from 195)

### Step 2: Fix api.ts imports (Group b) ✓
- Target: `src/lib/api.ts`
- Added all missing type imports from `@/types`
- **Build errors after: ~80**

### Step 3: Fix project-store.ts Location types (Group c) ✓
- Target: `src/lib/project-store.ts`
- Renamed `Location` import to `LocationType` to avoid conflict with global `Window.Location`
- Updated all Location references in state and actions
- Fixed Story Engine action types (unknown[] → Record<string, unknown>[])
- Fixed generatePrompt prompt_type type (string → PromptType)
- Added missing `projects`, `fetchProjects`, `selectedScene`, `setSelectedScene` to ProjectState
- **Build errors after: ~30**

### Step 4: Fix remaining page errors (Group d) ✓
- **assets/page.tsx**: Fixed AssetType to use `[number]`, added Input/Textarea imports, fixed event handler types
- **dialogues/page.tsx**: Added episodeId derivation from selectedScene, fixed fetchDialogues/createDialogue/updateDialogue/deleteDialogue calls, fixed dialogues access (Record<string, Dialogue[]> → Dialogue[])
- **episodes/page.tsx**: Fixed formData episode_number to string, explicit property assignment in create/update, fixed implicit any in map callbacks
- **flow/page.tsx**: Fixed TaskType to use `[number]`, added explicit type to formData useState
- **page.tsx (dashboard)**: Fixed api.listProjects response to use `.items` and `.total`
- **projects/page.tsx**: Fixed api.listProjects response to use `.items` and `.total_pages`, converted Select to Radix-style API, fixed implicit any in filter callbacks
- **series-bible/page.tsx**: Parse JSON strings for subplots and character_relationships before saving
- **prompts/page.tsx**: Already fixed via Textarea fontMono support

---

## Build Results Tracking

| Step | Command | Errors Remaining | Notes |
|------|---------|------------------|-------|
| Initial | `npm run build` | 195 | Baseline from log |
| After Select fix | `npm run build` | ~120 | Select API, Input/Textarea created |
| After api.ts fix | `npm run build` | ~80 | All types imported |
| After project-store fix | `npm run build` | ~30 | Location types, new state props |
| After page fixes | `npm run build` | **0** | All type errors resolved |
| Final | `npm run build` | **0** | Exit 0, all pages generated |

---

## Final Verification

- ✅ `cd frontend && npm run build` → **exit 0**, 0 errors, 18 pages generated
- ✅ `cd backend && ./venv/bin/python -m pytest tests/ -q` → **40 passed**