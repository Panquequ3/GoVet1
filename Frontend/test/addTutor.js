import { By, Key, Builder, until } from 'selenium-webdriver';
import { getValidToken } from '../sessionManager.js';
import * as chai from "chai";

const should = chai.should();

describe("Pruebas de Tutores con API", function() {
    let driver;
    let token;
    const TEST_RUT = "99.999.999-9";
    const DELAY_DEMO = 2000;
    const VERIFY_SUCCESS_TOAST = true;
    const SUCCESS_TOAST_TEXT = "Tutor registrado exitosamente";

    async function waitForSuccessToast(expectedMessage, timeout = 6000) {
        await driver.wait(
            until.elementLocated(By.css("ion-toast.toast-success")),
            timeout
        );

        await driver.wait(async () => {
            return await driver.executeScript(
                `
                const toast = document.querySelector('ion-toast.toast-success');
                if (!toast) return false;

                const isHidden = toast.classList.contains('overlay-hidden') || toast.classList.contains('toast-hidden');
                const message = toast.shadowRoot?.querySelector('.toast-message')?.textContent?.trim() || '';

                return !isHidden && message.includes(arguments[0]);
                `,
                expectedMessage
            );
        }, timeout);
    }

    before(async function() {
        // Obtener el token del backdoor
        token = await getValidToken();

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

    it("Debería ir a el apartado de añadir y añadir el tutor", async function() {
        // Ir a el añadir
        await driver.get("http://localhost:3007/registro-tutor");
        await driver.sleep(DELAY_DEMO);

        // Buscar todos los inputs

        // Nombre
        const nombreInput = await driver.wait(
            until.elementLocated(By.css("#nombre_id input")),
            2000
        );
        await nombreInput.click();
        await driver.sleep(800);
        await nombreInput.sendKeys("Martin", Key.TAB);
        await driver.sleep(800);

        // Apellidos
        const apellido1Input = await driver.wait(
            until.elementLocated(By.css("#apellido_id_1 input")),
            2000
        );
        await apellido1Input.click();
        await driver.sleep(800);
        await apellido1Input.sendKeys("Jaque", Key.TAB);
        await driver.sleep(800);

        const apellido2Input = await driver.wait(
            until.elementLocated(By.css("#apellido_id_2 input")),
            2000
        );
        await apellido2Input.click();
        await driver.sleep(800);
        await apellido2Input.sendKeys("Lobos", Key.TAB);
        await driver.sleep(800);


        // Rut
        const rutInput = await driver.wait(
            until.elementLocated(By.css("#rut_id input")),
            2000
        );
        await rutInput.click();
        await driver.sleep(800);
        await rutInput.sendKeys(TEST_RUT, Key.TAB);
        await driver.sleep(800);


        // Direccion
        const direccionInput = await driver.wait(
            until.elementLocated(By.css("#direccion_id input")),
            2000
        );
        await direccionInput.click();
        await driver.sleep(800);
        await direccionInput.sendKeys("Alguna Parte de Las Animas", Key.TAB);
        await driver.sleep(800);


        // Telefono
        const telefonoInput = await driver.wait(
            until.elementLocated(By.css("#id_telefono input")),
            2000
        );
        await telefonoInput.click();
        await driver.sleep(800);
        await telefonoInput.sendKeys("99999999", Key.TAB);
        await driver.sleep(500);

        // Logica de region

        const regionList = await driver.wait(
            until.elementLocated(By.css("#region_id input")),
            2000
        );
        await regionList.click();
        await driver.sleep(500);

        await regionList.sendKeys("V");
        await driver.sleep(1000);

        const regionOption = await driver.wait(
            until.elementLocated(By.css("ion-item[id='region_option']")),
            2000
        );
        await regionOption.click();
        await driver.sleep(500);
        
        //Scroll y

        const registroButton = await driver.wait(
            until.elementLocated(By.css("#registrar_id")),
            2000
        );
        await driver.executeScript("arguments[0].scrollIntoView(true);", registroButton); //Para el scroll, modificar el 300 en caso de
        await driver.sleep(500);

        // Logica de comuna
        const comunaList = await driver.wait(
            until.elementLocated(By.css("#comuna_id input")),
            2000
        );
        await comunaList.click();
        await driver.sleep(500);

        await comunaList.sendKeys("Ar");
        await driver.sleep(1000);

        const comunaOption = await driver.wait(
            until.elementLocated(By.css("ion-item[id='comuna_option']")),
            2000
        );
        await comunaOption.click();
        await driver.sleep(800);

        // Email

        const emailInput = await driver.wait(
            until.elementLocated(By.css("#email_id input")),
            2000
        );
        await emailInput.click();
        await driver.sleep(800);
        await emailInput.sendKeys("govet@paw-solutions.com", Key.TAB);
        await driver.sleep(800);

        // Luego de esto debe terminar
        
        await registroButton.click();
        await driver.sleep(500);

        if (VERIFY_SUCCESS_TOAST) {
            await waitForSuccessToast(SUCCESS_TOAST_TEXT);
            console.log("Toast de exito detectado correctamente.");
        }


        console.log("Test completado: Tutor añadido.");

    });
});

//Farmeando commits MUAHAAHAHHAHAH