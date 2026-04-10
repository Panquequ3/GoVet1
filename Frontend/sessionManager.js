import fs from "fs";

async function getValidToken() {
    const path = './session_data.json';
    
    // Si exite el archivo
    if (fs.existsSync(path)) {
        const session = JSON.parse(fs.readFileSync(path));
        return session.token;
    }


    // Obtiene credenciales de login de dev
    const response = await fetch("http://localhost:4007/api/dev_login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: "test@tusistema.com" })
    });

    const data = await response.json();

    // Guarda credenciales
    if (data.sessionToken) {
        fs.writeFileSync(path, JSON.stringify({ token: data.sessionToken }));
        return data.sessionToken;
        
    }

    throw new Error("No se pudo obtener el token del backdoor");
}


export {getValidToken};