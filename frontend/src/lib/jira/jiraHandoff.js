/**
 * The handoff between the chat and the Jira window.
 *
 * Both pages are the same origin, so the draft travels through local storage rather than a new
 * collection and a polling loop. The chat writes a draft and a link back to the conversation
 * that produced it; the Jira window reads both, so you can go chat -> Jira -> back to the exact
 * conversation instead of hunting for it again.
 */

// What the Jira window is editing right now.
const DRAFT_KEY = 'pami.jira.draft';
// What the chat has just produced and the Jira window has not accepted yet. Separate on
// purpose: writing straight into DRAFT_KEY threw away a half-written ticket the moment you
// asked PAMI for a new one, with no warning and no way back.
const INCOMING_KEY = 'pami.jira.incoming';
const ORIGIN_KEY = 'pami.jira.draftOrigin';

const read = (key) => {
    try {
        return window.localStorage.getItem(key);
    } catch (error) {
        return null;
    }
};

const write = (key, value) => {
    try {
        if (value === null) window.localStorage.removeItem(key);
        else window.localStorage.setItem(key, value);
    } catch (error) {
        /* a blocked localStorage only costs the handoff */
    }
};

/** Store a draft the chat produced, plus where it came from. Never overwrites the editor. */
export const stashDraft = (draft, origin) => {
    write(INCOMING_KEY, JSON.stringify(draft));
    write(ORIGIN_KEY, origin ? JSON.stringify(origin) : null);
};

const readJson = (key) => {
    const raw = read(key);
    if (!raw) return null;
    try {
        const parsed = JSON.parse(raw);
        return parsed && typeof parsed === 'object' ? parsed : null;
    } catch (error) {
        return null;
    }
};

/** A draft the chat produced that the Jira window has not taken yet. */
export const readIncomingDraft = () => readJson(INCOMING_KEY);

export const clearIncomingDraft = () => write(INCOMING_KEY, null);

export const readStashedDraft = () => readJson(DRAFT_KEY);

/** Whether a stored ticket has anything in it worth protecting. */
export const draftHasContent = (draft) =>
    Boolean(draft && (draft.summary || '').trim()) ||
    Boolean(draft && (draft.description || '').trim());

/** Which conversation the current draft came from, if any. */
export const readDraftOrigin = () => {
    const raw = read(ORIGIN_KEY);
    if (!raw) return null;
    try {
        const parsed = JSON.parse(raw);
        return parsed?.conversationId ? parsed : null;
    } catch (error) {
        return null;
    }
};

export const clearDraftOrigin = () => write(ORIGIN_KEY, null);

/** The ticket shape the chat sends and the Jira window edits. */
export const draftFromApi = (api, fallback) => ({
    templateId: api?.template_id || fallback?.templateId || 'story',
    projectKey: fallback?.projectKey || '',
    issueType: api?.issue_type || fallback?.issueType || 'Story',
    summary: api?.summary ?? fallback?.summary ?? '',
    description: api?.description ?? fallback?.description ?? '',
    assigneeAccountId: fallback?.assigneeAccountId || '',
    priority: api?.priority || '',
    dueDate: api?.due_date || '',
    labels: api?.labels?.length ? api.labels : fallback?.labels || ['pami']
});
