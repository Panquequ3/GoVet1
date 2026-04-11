import { useState, useRef, useEffect, useMemo } from "react";
import {
  IonPage,
  IonHeader,
  IonToolbar,
  IonTitle,
  IonContent,
  IonList,
  IonItem,
  IonLabel,
  IonInput,
  IonSelect,
  IonSelectOption,
  IonRadioGroup,
  IonRadio,
  IonButton,
  IonButtons,
  IonGrid,
  IonRow,
  IonCol,
  IonToast,
  IonText,
  IonIcon,
} from "@ionic/react";
import { close } from "ionicons/icons";
import "../styles/registroTutor.css";
import InputTelefono, {
  InputTelefonoHandle,
} from "../components/registroTutor/inputTelefono";
import InputRut, { InputRutHandle } from "../components/registroTutor/inputRut";
import { SelectorRegion } from "../components/registroTutor/SelectorRegion";
import { SelectorComuna } from "../components/registroTutor/SelectorComuna";
import { crearTutor } from "../api/tutores";
import { obtenerRegiones } from "../api/regiones";
import { formatRegionName, formatComunaName } from "../utils/formatters";
import { useAuth } from "../hooks/useAuth";
// Componente: Interfaz para gestionar dueños

// FUNCIÓN DE NORMALIZACIÓN PARA BÚSQUEDA ROBUSTA
const normalizarTexto = (texto: string) => {
  if (!texto) return "";
  return texto
    .toLowerCase() // A minúsculas
    .normalize("NFD") // Descomponer caracteres (á -> a + ´)
    .replace(/[\u0300-\u036f]/g, "") // Eliminar diacríticos (acentos)
    .replace(/\s+/g, ""); // Eliminar TODOS los espacios
};

interface RegistroTutorProps {
  onClose?: () => void;
  onTutorRegistered?: (tutor: any) => void;
}

const RegistroTutor: React.FC<RegistroTutorProps> = ({
  onClose,
  onTutorRegistered,
}) => {
  const { sessionToken } = useAuth();
  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState("");
  const [toastColor, setToastColor] = useState<
    "success" | "danger" | "warning"
  >("success");
  const [isLoading, setIsLoading] = useState(false);

  // Estados para regiones y comunas (similar a especies y razas)
  const [regiones, setRegiones] = useState<any[]>([]);
  const [loadingRegiones, setLoadingRegiones] = useState(false);
  const [regionQuery, setRegionQuery] = useState("");
  const [showRegionList, setShowRegionList] = useState(false);
  const [selectedRegion, setSelectedRegion] = useState<any>(null);
  const [comunaQuery, setComunaQuery] = useState("");
  const [showComunaList, setShowComunaList] = useState(false);
  const [selectedComuna, setSelectedComuna] = useState<{
    id: string;
    name: string;
  } | null>(null);

  // Estado para los campos del formulario
  const [formData, setFormData] = useState({
    nombre: "",
    apellido_paterno: "",
    apellido_materno: "",
    rut: "",
    direccion: "",
    celular: 0,
    celular2: 0,
    telefono: 0,
    telefono2: 0,
    comuna: "",
    region: "",
    email: "",
    observacion: "",
  });

  // Cargar regiones al inicializar
  useEffect(() => {
    const fetchRegiones = async () => {
      try {
        setLoadingRegiones(true);
        const data = await obtenerRegiones();
        //console.log("✅ Regiones cargadas:", data);
        //console.log("📊 Cantidad de regiones:", data?.length);
        setRegiones(data);
      } catch (error) {
        console.error("❌ Error cargando regiones:", error);
        setToastMessage("Error al cargar regiones");
        setToastColor("danger");
        setShowToast(true);
      } finally {
        setLoadingRegiones(false);
      }
    };

    fetchRegiones();
  }, []);

  // Filtrar regiones basado en la búsqueda con normalización fuzzy
  const filteredRegiones = useMemo(() => {
    const filtered = regiones.filter((region) => {
      // Si no hay búsqueda, mostrar todas las regiones
      if (!regionQuery.trim()) {
        return true;
      }
      // Normalizar término de búsqueda
      const terminoNormalizado = normalizarTexto(regionQuery);

      // Normalizar nombre formateado y nombre original
      const formattedName = formatRegionName(region);
      const nombreFormateadoNormalizado = normalizarTexto(formattedName);
      const nombreOriginalNormalizado = normalizarTexto(region.name);

      return (
        nombreFormateadoNormalizado.includes(terminoNormalizado) ||
        nombreOriginalNormalizado.includes(terminoNormalizado)
      );
    });

    /*console.log(
      "🔍 Regiones filtradas:",
      filtered.length,
      "de",
      regiones.length
    );*/
    //console.log("🔍 Búsqueda actual:", regionQuery);
    return filtered;
  }, [regiones, regionQuery]);

  // Filtrar comunas basado en la región seleccionada y la búsqueda con normalización fuzzy
  const filteredComunas = useMemo(() => {
    if (!selectedRegion) return [];
    const region = regiones.find((r) => r.id === selectedRegion.id);
    if (!region || !region.communes) return [];

    return region.communes.filter((comuna: any) => {
      // Si no hay búsqueda, mostrar todas las comunas
      if (!comunaQuery.trim()) {
        return true;
      }
      // Normalizar término de búsqueda
      const terminoNormalizado = normalizarTexto(comunaQuery);

      // Normalizar nombre formateado y nombre original
      const formattedName = formatComunaName(comuna.name);
      const nombreFormateadoNormalizado = normalizarTexto(formattedName);
      const nombreOriginalNormalizado = normalizarTexto(comuna.name);

      return (
        nombreFormateadoNormalizado.includes(terminoNormalizado) ||
        nombreOriginalNormalizado.includes(terminoNormalizado)
      );
    });
  }, [regiones, selectedRegion, comunaQuery]);

  // Función para seleccionar región (actualizada)
  const selectRegion = (id: string, name: string, fullRegion: any) => {
    setSelectedRegion(fullRegion);
    setRegionQuery(name);
    setShowRegionList(false);

    // Limpiar comuna cuando se cambia la región
    setSelectedComuna(null);
    setComunaQuery("");
    setShowComunaList(false);
  };

  // Función para seleccionar comuna (actualizada)
  const selectComuna = (id: string, name: string) => {
    setSelectedComuna({ id, name });
    setComunaQuery(name);
    setShowComunaList(false);
  };

  // Referencias para resetear componentes
  const inputRutRef = useRef<InputRutHandle>(null);
  const resetRut = () => {
    inputRutRef.current?.reset();
  };

  const inputTelefonoRef = useRef<InputTelefonoHandle>(null);
  const resetTelefono = () => {
    inputTelefonoRef.current?.reset();
  };

  const handlePhoneChange = (phone: string) => {
    const cleaned = phone.replace(/\D/g, "");
    const startIndex = cleaned.indexOf("9");
    const phoneDigits = cleaned.slice(startIndex);
    const phoneAsNumber = parseInt(phoneDigits, 10);

    setFormData((prevState) => ({
      ...prevState,
      telefono: isNaN(phoneAsNumber) ? 0 : phoneAsNumber,
    }));
  };

  const handleRutChange = (rut: string) => {
    setFormData((prevState) => ({
      ...prevState,
      rut: rut,
    }));
  };

  // Manejador de cambios en los inputs
  const handleInputChange = (e: any) => {
    const { name, value } = e.target;
    setFormData((prevState) => ({
      ...prevState,
      [name]: value,
    }));
  };

  // Expresión regular para validar correos electrónicos
  const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/i;

  // Función para registrar tutor
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    // Validación de campos obligatorios
    if (
      !formData.nombre.trim() ||
      !formData.apellido_paterno.trim() ||
      !formData.rut.trim() ||
      !formData.email.trim() ||
      !formData.telefono ||
      !selectedRegion ||
      !selectedComuna
    ) {
      setToastMessage("Complete todos los campos obligatorios");
      setToastColor("warning");
      setShowToast(true);
      setIsLoading(false);
      return;
    }

    // Validación de correo
    if (!emailRegex.test(formData.email)) {
      setToastMessage("Ingrese un correo válido");
      setToastColor("warning");
      setShowToast(true);
      setIsLoading(false);
      return;
    }

    try {
      // Actualizar formData con región y comuna seleccionadas (nombres formateados)
      const dataToSubmit = {
        ...formData,
        region: selectedRegion ? formatRegionName(selectedRegion) : "",
        comuna: selectedComuna ? selectedComuna.name : "",
      };

      const respuesta = await crearTutor(dataToSubmit, sessionToken);
      //console.log("Tutor creado:", respuesta);
      setToastMessage("Tutor registrado exitosamente");
      setToastColor("success");

      // Si hay callback, invocar con los datos del tutor creado
      if (onTutorRegistered && respuesta) {
        const tutorData = {
          rut: respuesta.rut,
          nombre: respuesta.nombre,
          apellido: `${respuesta.apellido_paterno}${
            respuesta.apellido_materno ? " " + respuesta.apellido_materno : ""
          }`,
          telefono: respuesta.telefono?.toString() || "",
          email: respuesta.email || "",
          direccion: respuesta.direccion || "",
          comuna: respuesta.comuna || "",
          region: respuesta.region || "",
        };
        onTutorRegistered(tutorData);
      }

      // Limpiar formulario
      setFormData({
        nombre: "",
        apellido_materno: "",
        apellido_paterno: "",
        rut: "",
        direccion: "",
        telefono: 0,
        telefono2: 0,
        comuna: "",
        region: "",
        celular: 0,
        celular2: 0,
        email: "",
        observacion: "",
      });

      // Resetear selectores
      setRegionQuery("");
      setComunaQuery("");
      setSelectedRegion(null);
      setSelectedComuna(null);
      setShowRegionList(false);
      setShowComunaList(false);

      resetRut();
      resetTelefono();

      // Cerrar el modal si fue abierto desde registro de paciente
      if (onClose && onTutorRegistered) {
        onClose();
      }
    } catch (error) {
      console.error("Fallo al crear tutor:", error);
      setToastMessage("Error de conexión");
      setToastColor("danger");
    } finally {
      setIsLoading(false);
      setShowToast(true);
    }
  };

  return (
    <IonPage>
      <IonHeader translucent={true}>
        <IonToolbar>
          <IonTitle>Registrar Tutor</IonTitle>
          {onClose && (
            <IonButtons slot="end">
              <IonButton onClick={onClose}>
                <IonIcon icon={close} slot="icon-only" />
              </IonButton>
            </IonButtons>
          )}
        </IonToolbar>
      </IonHeader>
      <IonContent fullscreen={true}>
        <IonHeader collapse="condense">
          <IonToolbar>
            <IonTitle size="large">Registrar Tutor</IonTitle>
          </IonToolbar>
        </IonHeader>
        <IonList>
          <IonGrid>
            <IonRow>
              <IonCol>
                <IonItem lines="none">
                  <IonInput
                    id="nombre_id"
                    type="text"
                    labelPlacement="stacked"
                    fill="outline"
                    placeholder="Daniela"
                    name="nombre"
                    value={formData.nombre}
                    onIonChange={handleInputChange}
                  >
                    <div slot="label">
                      Nombre <IonText color="danger">(*)</IonText>
                    </div>
                  </IonInput>
                </IonItem>
              </IonCol>
            </IonRow>
            {/* Input Apellidos */}
            <IonRow className="apellidos">
              <IonCol>
                <IonItem lines="none" className="apellido-paterno">
                  <IonInput
                    id="apellido_id_1"
                    required
                    type="text"
                    labelPlacement="stacked"
                    fill="outline"
                    placeholder="Huenuman"
                    name="apellido_paterno"
                    value={formData.apellido_paterno}
                    onIonChange={handleInputChange}
                  >
                    <div slot="label">
                      Primer Apellido <IonText color="danger">(*)</IonText>
                    </div>
                  </IonInput>
                </IonItem>
              </IonCol>
              <IonCol>
                <IonItem lines="none" className="apellido-materno">
                  <IonInput
                    id="apellido_id_2"
                    className="apellido-materno"
                    label="Segundo Apellido"
                    type="text"
                    labelPlacement="stacked"
                    fill="outline"
                    placeholder="Oliva"
                    name="apellido_materno"
                    value={formData.apellido_materno}
                    onIonChange={handleInputChange}
                  ></IonInput>
                </IonItem>
              </IonCol>
            </IonRow>
            {/* Input RUT */}
            <IonRow>
              <IonCol>
                <InputRut onRutChange={handleRutChange} ref={inputRutRef} />
              </IonCol>
            </IonRow>
            {/* Input dirección */}
            <IonRow>
              <IonCol>
                <IonItem lines="none">
                  <IonInput
                    id="direccion_id"
                    type="text"
                    labelPlacement="stacked"
                    fill="outline"
                    placeholder="Calle Falsa 123"
                    name="direccion"
                    value={formData.direccion}
                    onIonChange={handleInputChange}
                  >
                    <div slot="label">
                      Dirección <IonText color="danger">(*)</IonText>
                    </div>
                  </IonInput>
                </IonItem>
              </IonCol>
            </IonRow>
            {/* Input Telefono */}
            <IonRow>
              <IonCol>
                <InputTelefono
                  onPhoneChange={handlePhoneChange}
                  ref={inputTelefonoRef}
                />
              </IonCol>
            </IonRow>
            {/* Selector Región */}
            <IonRow>
              <IonCol>
                <SelectorRegion
                  regionQuery={regionQuery}
                  setRegionQuery={setRegionQuery}
                  showRegionList={showRegionList}
                  setShowRegionList={setShowRegionList}
                  filteredRegiones={filteredRegiones}
                  loadingRegiones={loadingRegiones}
                  selectRegion={selectRegion}
                />
              </IonCol>
            </IonRow>
            {/* Selector Comuna */}
            <IonRow>
              <IonCol>
                <SelectorComuna
                  comunaQuery={comunaQuery}
                  setComunaQuery={setComunaQuery}
                  showComunaList={showComunaList}
                  setShowComunaList={setShowComunaList}
                  filteredComunas={filteredComunas}
                  loadingComunas={false}
                  selectComuna={selectComuna}
                  regionSeleccionada={!!selectedRegion}
                />
              </IonCol>
            </IonRow>
            {/* Input Email */}
            <IonRow>
              <IonCol>
                <IonItem lines="none">
                  <IonInput
                    id="email_id"
                    required
                    type="email"
                    labelPlacement="stacked"
                    fill="outline"
                    placeholder="govet@paw-solutions.com"
                    name="email"
                    value={formData.email}
                    onIonChange={handleInputChange}
                  >
                    <div slot="label">
                      Email <IonText color="danger">(*)</IonText>
                    </div>
                  </IonInput>
                </IonItem>
              </IonCol>
            </IonRow>
          </IonGrid>
          {/* Botón Registrar Tutor */}
          <IonRow>
            <IonCol className="ion-text-center">
              <IonButton
                id="registrar_id"
                type="submit"
                className="custom-button"
                expand="block"
                onClick={handleSubmit}
                disabled={isLoading}
              >
                {isLoading ? "Registrando..." : "Registrar tutor"}
              </IonButton>
            </IonCol>
          </IonRow>
        </IonList>
        <IonToast
          isOpen={showToast}
          onDidDismiss={() => setShowToast(false)}
          message={toastMessage}
          duration={3000}
          position="bottom"
          color={toastColor}
          cssClass={
            toastColor === "success"
              ? "toast-success"
              : toastColor === "danger"
              ? "toast-error"
              : "toast-warning"
          }
        />
      </IonContent>
    </IonPage>
  );
};

export default RegistroTutor;
