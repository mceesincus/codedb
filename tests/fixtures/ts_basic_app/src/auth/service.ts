import { decodeJwt } from "./jwt"

export class AuthService {
  validateToken(token: string) {
    return decodeJwt(token)
  }
}

export function buildAuthService() {
  return new AuthService()
}

