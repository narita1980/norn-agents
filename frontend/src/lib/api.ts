export type PostMessageRequest = {
  thread_id: string | null;
  content: string;
};

export type PostMessageResponse = {
  thread_id: string;
  message_id: string;
  reply: string;
};

export async function postMessage(body: PostMessageRequest): Promise<PostMessageResponse> {
  const response = await fetch('/chat/messages', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return (await response.json()) as PostMessageResponse;
}
