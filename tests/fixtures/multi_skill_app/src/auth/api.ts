import { AuthService } from "./service"

export function loginHandler(token: string) {
  const service = new AuthService()
  return service.validateToken(token)
}
