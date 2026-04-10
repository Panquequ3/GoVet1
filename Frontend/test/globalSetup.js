import { getValidToken } from '../sessionManager.js';

export const mochaHooks = {
  async beforeAll() {
    console.log("-----------------------------------------");
    console.log("COMPROBANDO SESIÓN DEV...");
    console.log("-----------------------------------------");
    
    global.ACTIVE_SESSION_TOKEN = await getValidToken();
    console.log("-----------------------------------------");
    console.log("SESIÓN LISTA. INICIANDO TESTS...");
    console.log("-----------------------------------------");
  }
};