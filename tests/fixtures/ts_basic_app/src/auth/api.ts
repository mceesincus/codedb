import { buildAuthService } from "./service"

export function loginHandler(token: string) {
  const service = buildAuthService()
  return service.validateToken(token)
}

