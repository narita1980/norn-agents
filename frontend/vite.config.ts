import { defineConfig, loadEnv, type Connect, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';

const BACKEND = 'http://localhost:8000';
const BASIC_AUTH_REALM = 'Basic realm="Norn"';

type AuthRequest = Connect.IncomingMessage & {
  headers: Record<string, string | string[] | undefined>;
};

function getAuthorizationHeader(req: AuthRequest): string | undefined {
  const raw = req.headers.authorization ?? req.headers.Authorization;
  return Array.isArray(raw) ? raw[0] : raw;
}

function basicAuthMiddleware(
  username: string,
  password: string,
): Connect.NextHandleFunction {
  return (req, res, next) => {
    const authHeader = getAuthorizationHeader(req as AuthRequest);
    if (!authHeader?.startsWith('Basic ')) {
      res.statusCode = 401;
      res.setHeader('WWW-Authenticate', BASIC_AUTH_REALM);
      res.end('Unauthorized');
      return;
    }

    let decoded: string;
    try {
      decoded = atob(authHeader.slice(6));
    } catch {
      res.statusCode = 401;
      res.setHeader('WWW-Authenticate', BASIC_AUTH_REALM);
      res.end('Unauthorized');
      return;
    }

    const sep = decoded.indexOf(':');
    if (sep === -1) {
      res.statusCode = 401;
      res.setHeader('WWW-Authenticate', BASIC_AUTH_REALM);
      res.end('Unauthorized');
      return;
    }

    const user = decoded.slice(0, sep);
    const pwd = decoded.slice(sep + 1);
    if (user !== username || pwd !== password) {
      res.statusCode = 401;
      res.setHeader('WWW-Authenticate', BASIC_AUTH_REALM);
      res.end('Unauthorized');
      return;
    }

    next();
  };
}

function basicAuthDevPlugin(username: string, password: string): Plugin {
  return {
    name: 'norn-basic-auth',
    configureServer(server) {
      if (!username || !password) return;
      server.middlewares.use(basicAuthMiddleware(username, password));
    },
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '../backend', '');
  const username = env.NORN_BASIC_AUTH_USERNAME ?? '';
  const password = env.NORN_BASIC_AUTH_PASSWORD ?? '';
  const swaBuild = mode === 'swa';

  return {
    plugins: [react(), basicAuthDevPlugin(username, password)],
    build: {
      outDir: swaBuild ? 'dist' : '../backend/norn/static',
      emptyOutDir: true,
    },
    server: {
      port: 5173,
      proxy: {
        '/chat': BACKEND,
        '/webhook': BACKEND,
        '/reviews': BACKEND,
        '/dashboard': BACKEND,
        '/healthz': BACKEND,
        '/readyz': BACKEND,
      },
    },
  };
});
