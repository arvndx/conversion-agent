import { get, post } from './client'

export function sendAgentMessage(profileId, message, pageContext) {
  return post(`/agent/conversations/${profileId}/messages`, { message, page_context: pageContext })
}

export function greetAgent(profileId, pageContext) {
  return post(`/agent/conversations/${profileId}/greet`, { page_context: pageContext })
}

export function getAgentConversation(profileId) {
  return get(`/agent/conversations/${profileId}`)
}

export function resumeAfterHandoff(profileId, pageContext) {
  return post(`/agent/conversations/${profileId}/resume-after-handoff`, { page_context: pageContext })
}

export function startTourBatch(profileId, pageContext) {
  return post(`/agent/conversations/${profileId}/tour/start`, { page_context: pageContext })
}
