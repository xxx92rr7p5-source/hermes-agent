import type * as React from 'react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Codicon } from '@/components/ui/codicon'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { DisclosureCaret } from '@/components/ui/disclosure-caret'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { SanitizedInput } from '@/components/ui/sanitized-input'
import { useI18n } from '@/i18n'
import { gitRef } from '@/lib/sanitize'
import { cn } from '@/lib/utils'
import { notifyError } from '@/store/notifications'
import { copyPath, revealPath, startWorkInRepo } from '@/store/projects'

import { SidebarCount, SidebarRowLead } from '../chrome'

// "+" affordance shared by repo and worktree headers — reveals on header hover.
export function WorkspaceAddButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      aria-label={label}
      className="grid size-4 shrink-0 place-items-center rounded-sm bg-transparent text-(--ui-text-quaternary) opacity-0 transition-opacity hover:bg-(--ui-control-hover-background) hover:text-foreground group-hover/workspace:opacity-100"
      onClick={onClick}
      type="button"
    >
      <Codicon name="add" size="0.75rem" />
    </button>
  )
}

// Reveals the next page of already-loaded rows within a workspace/worktree.
export function WorkspaceShowMoreButton({ count, label, onClick }: { count: number; label: string; onClick: () => void }) {
  const { t } = useI18n()
  const text = t.sidebar.showMoreIn(count, label)

  return (
    <button
      aria-label={text}
      className="ml-auto grid size-5 place-items-center rounded-sm bg-transparent text-(--ui-text-tertiary) transition-colors hover:bg-(--ui-control-hover-background) hover:text-foreground"
      onClick={onClick}
      type="button"
    >
      <Codicon name="ellipsis" size="0.75rem" />
    </button>
  )
}

// Per-worktree actions (linked worktree lanes only), mirroring the session row
// and ProjectMenu kebab: reveal in the file manager, copy path, and remove the
// worktree (runs a real `git worktree remove` via the caller's confirm dialog).
export function WorkspaceMenu({ path, onRemove }: { path: null | string; onRemove: () => void }) {
  const { t } = useI18n()
  const p = t.sidebar.projects

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          aria-label={p.menu}
          className="grid size-4 shrink-0 place-items-center rounded-sm bg-transparent text-(--ui-text-quaternary) opacity-0 transition-opacity hover:bg-(--ui-control-hover-background) hover:text-foreground group-hover/workspace:opacity-100 data-[state=open]:opacity-100"
          onClick={event => event.stopPropagation()}
          type="button"
        >
          <Codicon name="kebab-vertical" size="0.75rem" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48" sideOffset={6}>
        <DropdownMenuItem disabled={!path} onSelect={() => void revealPath(path)}>
          <Codicon name="folder-opened" size="0.875rem" />
          <span>{p.reveal}</span>
        </DropdownMenuItem>
        <DropdownMenuItem disabled={!path} onSelect={() => void copyPath(path)}>
          <Codicon name="copy" size="0.875rem" />
          <span>{p.copyPath}</span>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={onRemove} variant="destructive">
          <Codicon name="trash" size="0.875rem" />
          <span>{`${p.removeWorktree}…`}</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

// "New worktree": prompt for a branch name, then git spins up a fresh worktree
// for that branch under the repo (the lightest way) and we open a new session
// inside it. Naming is explicit — no auto-generated `hermes/work-<ts>` trees.
export function StartWorkButton({ repoPath, onStarted }: { repoPath: string; onStarted: (path: string) => void }) {
  const { t } = useI18n()
  const s = t.sidebar
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [pending, setPending] = useState(false)

  const submit = async () => {
    const branch = name.trim()

    if (pending || !repoPath || !branch) {
      return
    }

    setPending(true)

    try {
      // Pass the typed value as both the dir slug source and the branch, so the
      // branch is exactly what the user named (the dir is slugified git-side).
      const result = await startWorkInRepo(repoPath, { branch, name: branch })

      if (result) {
        onStarted(result.path)
        setOpen(false)
        setName('')
      }
    } catch (err) {
      notifyError(err, s.projects.startWorkFailed)
    } finally {
      setPending(false)
    }
  }

  return (
    <>
      <button
        aria-label={s.projects.startWork}
        className="grid size-4 shrink-0 place-items-center rounded-sm bg-transparent text-(--ui-text-quaternary) opacity-0 transition-opacity hover:bg-(--ui-control-hover-background) hover:text-foreground group-hover/section:opacity-100 focus-visible:opacity-100"
        onClick={() => setOpen(true)}
        type="button"
      >
        <Codicon name="git-branch" size="0.75rem" />
      </button>
      <Dialog onOpenChange={setOpen} open={open}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{s.projects.newWorktreeTitle}</DialogTitle>
            <DialogDescription>{s.projects.newWorktreeDesc}</DialogDescription>
          </DialogHeader>
          <SanitizedInput
            autoFocus
            disabled={pending}
            onKeyDown={event => {
              if (event.key === 'Enter') {
                event.preventDefault()
                void submit()
              } else if (event.key === 'Escape') {
                setOpen(false)
              }
            }}
            onValueChange={setName}
            placeholder={s.projects.branchPlaceholder}
            sanitize={gitRef}
            value={name}
          />
          <DialogFooter>
            <Button disabled={pending} onClick={() => setOpen(false)} type="button" variant="ghost">
              {t.common.cancel}
            </Button>
            <Button disabled={pending || !name.trim()} onClick={() => void submit()} type="button">
              {s.projects.startWork}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

// Collapsible header shared by the repo (emphasis) and worktree levels: a toggle
// button with a leading glyph, plus an optional trailing action (the +).
export function WorkspaceHeader({
  action,
  count,
  emphasis = false,
  icon,
  label,
  onToggle,
  open
}: {
  action?: React.ReactNode
  count: React.ReactNode
  emphasis?: boolean
  icon: React.ReactNode
  label: string
  onToggle: () => void
  open: boolean
}) {
  return (
    <div
      className={cn(
        'group/workspace flex min-h-6 items-center gap-1 px-2 pt-1 text-[0.6875rem]',
        emphasis ? 'font-semibold text-(--ui-text-secondary)' : 'font-medium text-(--ui-text-tertiary)'
      )}
    >
      <button
        className={cn(
          'flex min-w-0 flex-1 items-center gap-1.5 bg-transparent text-left',
          emphasis ? 'hover:text-foreground' : 'hover:text-(--ui-text-secondary)'
        )}
        onClick={onToggle}
        type="button"
      >
        <SidebarRowLead>{icon}</SidebarRowLead>
        <span className="min-w-0 truncate">{label}</span>
        <span className="shrink-0">
          <SidebarCount>{count}</SidebarCount>
        </span>
        <DisclosureCaret
          className="shrink-0 text-(--ui-text-tertiary) opacity-0 transition group-hover/workspace:opacity-100"
          open={open}
        />
      </button>
      {action}
    </div>
  )
}
