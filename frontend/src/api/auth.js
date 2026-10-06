import { get, post } from './client'

export const getMe = () => get('/auth/me')
export const requestLoginCode = (email) => post('/auth/otp/request', { email })
export const verifyLoginCode = (email, code) => post('/auth/otp/verify', { email, code })
export const logout = () => post('/auth/logout')
export const getDemoProfiles = () => get('/auth/demo-profiles')
export const demoLogin = (profileId) => post('/auth/demo-login', { profile_id: profileId })
