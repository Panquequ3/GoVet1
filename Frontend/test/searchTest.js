import { By, Key, Builder, until } from 'selenium-webdriver';
import { getValidToken } from '../sessionManager.js';
import * as chai from "chai";

const should = chai.should();

describe("Pruebas de Tutores con API", function() {
    let driver;
    let token;
    const TEST_RUT = "99.999.999-9";
    const DELAY_DEMO = 2000;

    before(async function() {
        // Obtener el token del backdoor
        token = await getValidToken();

        // Crear el tutor de prueba
        const tutorData = {
            rut: TEST_RUT,
            nombre: "Tutor",
            apellido_paterno: "Prueba",
            apellido_materno: "Selenium",
            direccion: "Calle Test 123",
            comuna: "Valdivia",
            region: "Los Ríos",
            telefono: 912345678, 
            celular: 912345678,
            email: "test@govet.cl"
        };

        const response = await fetch("http://127.0.0.1:4007/api/tutores/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`,
                "Connection": "close" 
            },
            body: JSON.stringify(tutorData)
        });

        if (!response.ok) {
            const errorDetail = await response.json();
            console.log("ERROR DEL BACKEND:", JSON.stringify(errorDetail, null, 2));
            throw new Error(`Error ${response.status}: No se pudo crear el tutor`);
        }

        driver = await new Builder().forBrowser("firefox").build();
        
        // Cargar pagina para tener contexto
        await driver.get("http://localhost:3007/");

        // Inyectar el token
        await driver.executeScript(
            `localStorage.setItem('govet_session_token', '${token}');`
        );

        // Volver a la raiz para ser redireccionado y liberarse de la ruta login
        await driver.get("http://localhost:3007/");
    });

    after(async function() {
        await driver.sleep(3000);
        if (driver) await driver.quit();
        
        // Eliminar usuario de prueba
        await fetch(`http://localhost:4007/api/tutores/${TEST_RUT}`, {
            method: "DELETE",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
        });
    });

    it("Debería encontrar al tutor en la lista de búsqueda", async function() {
        await driver.get("http://localhost:3007/ver");
        await driver.sleep(DELAY_DEMO);

        const botonTutores = await driver.wait(
            until.elementLocated(By.css("#boton_busqueda_tutores")),
            2000
        );

        botonTutores.click();
        await driver.sleep(DELAY_DEMO);

        const buscadorInput = await driver.wait(
            until.elementLocated(By.css("#Barra_Busqueda input")), 
            15000 
        );

        await driver.wait(until.elementIsVisible(buscadorInput), 5000);

        await buscadorInput.clear();
        await buscadorInput.sendKeys(TEST_RUT, Key.ENTER);
        await driver.sleep(DELAY_DEMO);

        const filaTutor = await driver.wait(
        until.elementLocated(By.id(`tutor-item-${TEST_RUT}`)),
            10000 
        ); 

        const nombreVisible = await filaTutor.getText();
        nombreVisible.should.contain("Tutor Prueba");

        await filaTutor.click();
        await driver.sleep(DELAY_DEMO);

        console.log("Test completado: Tutor encontrado y detalle abierto.");


    });
});