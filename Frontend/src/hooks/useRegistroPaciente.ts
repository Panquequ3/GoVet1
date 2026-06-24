import { useState, useEffect, useCallback } from "react";
import { obtenerEspecies, obtenerRazas } from "../api/especies";
import {
  crearPaciente,
  asociarTutorAPaciente,
  PacienteCreate,
} from "../api/pacientes";
import { useAuth } from "./useAuth";
import * as Sentry from "@sentry/react";

Sentry.init({
  dsn: import.meta.env.VITE_SENTRY_DSN,
  integrations: [
    Sentry.browserTracingIntegration(),
  ],
  tracesSampleRate: 1.0,
});

export interface FormData {
  nombre: string;
  especie: any;
  raza: any;
  sexo: string;
  color: string;
  fechaNacimiento: string;
  codigo_chip: string;
  esterilizado: boolean;
  rut_tutor: string;
}

export const useRegistroPaciente = () => {
  const { sessionToken } = useAuth();
  const [formData, setFormData] = useState<FormData>({
    nombre: "",
    especie: null,
    raza: null,
    color: "",
    sexo: "",
    fechaNacimiento: "",
    esterilizado: false,
    codigo_chip: "",
    rut_tutor: "",
  });

  const [especiesData, setEspeciesData] = useState<any[]>([]);
  const [razasData, setRazasData] = useState<any[]>([]);
  const [loadingEspecies, setLoadingEspecies] = useState(false);
  const [loadingRazas, setLoadingRazas] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);

  const [especieQuery, setEspecieQuery] = useState("");
  const [razaQuery, setRazaQuery] = useState("");
  const [showEspecieList, setShowEspecieList] = useState(false);
  const [showRazaList, setShowRazaList] = useState(false);

  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState("");

  const handleCargarRazas = useCallback(async (nombreEspecie: string) => {
    //console.log("🔄 Cargando razas para:", nombreEspecie);
    setLoadingRazas(true);
    try {
        const razas = await obtenerRazas(nombreEspecie);
        setRazasData(razas || []);
    } catch (error) {
        Sentry.captureException(error);
        console.error("Error cargando razas:", error);
        setRazasData([]);
        setToastMessage("Error de conexión al cargar razas");
        setShowToast(true);
    } finally {
        setLoadingRazas(false);
    }
  }, []);

  const handleCargarEspecies = useCallback(async () => {
    //console.log("🔄 Iniciando carga de especies...");
    setLoadingEspecies(true);
    try {
      const especies = await obtenerEspecies();
      //console.log("✅ Especies cargadas:", especies.length, "especies");
      setEspeciesData(especies);
    } catch (error) {
      console.error("❌ Error cargando especies:", error);
      setToastMessage("Error de conexión al cargar especies");
      setShowToast(true);
    } finally {
      setLoadingEspecies(false);
    }
  }, []);

  useEffect(() => {
    const loadInitialData = async () => {
      await handleCargarEspecies();
      setInitialLoading(false);
    };
    loadInitialData();
  }, [handleCargarEspecies]);

  useEffect(() => {
    if (formData.especie && especiesData.length > 0) {
      const especieSeleccionada = especiesData.find(
        (esp) => esp.id_especie === parseInt(formData.especie)
      );
      if (especieSeleccionada) {
        handleCargarRazas(especieSeleccionada.nombre_comun);
      }
    } else {
      setRazasData([]);
    }
  }, [formData.especie, handleCargarRazas]);

  const handleInputChange = (e: any) => {
    const { name, value } = e.target;
    setFormData((prevState) => ({
      ...prevState,
      [name]: value,
    }));
  };

  const selectEspecie = (especieId: number, especieNombre: string) => {
    setFormData((prev) => ({
      ...prev,
      especie: especieId.toString(),
      raza: "",
    }));
    setEspecieQuery(especieNombre);
    setShowEspecieList(false);
    setRazaQuery("");
  };

  const selectRaza = (razaId: number, razaNombre: string) => {
    setFormData((prev) => ({
      ...prev,
      raza: razaId.toString(),
    }));
    setRazaQuery(razaNombre);
    setShowRazaList(false);
  };

  // Nueva función para limpiar especie y raza
  const clearEspecie = () => {
    setFormData((prev) => ({
      ...prev,
      especie: "",
      raza: "",
    }));
    setRazaQuery("");
    setRazasData([]); // Limpiar las razas disponibles
  };

  const registraPaciente = async () => {
    try {
      //console.log("📋 FormData completo antes de enviar:", formData);

      if (
        !formData.nombre ||
        !formData.raza ||
        !formData.sexo ||
        !formData.color ||
        !formData.fechaNacimiento ||
        !formData.rut_tutor
      ) {
        setToastMessage(
          "Por favor completa todos los campos requeridos y selecciona un tutor"
        );
        setShowToast(true);
        return;
      }

      // PASO 1: Crear el paciente (SIN rut_tutor)
      const pacienteData: PacienteCreate = {
        nombre: formData.nombre,
        id_raza: parseInt(formData.raza),
        sexo: formData.sexo,
        color: formData.color,
        fecha_nacimiento: formData.fechaNacimiento,
        codigo_chip: formData.codigo_chip || "",
        esterilizado: formData.esterilizado,
      };

      //console.log("📤 Datos del paciente que se enviarán:", pacienteData);

      const pacienteCreado = await crearPaciente(pacienteData, sessionToken);
      //console.log("✅ Paciente creado exitosamente:", pacienteCreado);

      // PASO 2: Asociar el tutor al paciente
      //console.log("🔗 Asociando tutor al paciente...");
      await asociarTutorAPaciente(
        formData.rut_tutor,
        pacienteCreado.id_paciente,
        new Date().toISOString().split("T")[0],
        sessionToken
      );
      //console.log("✅ Tutor asociado exitosamente");

      setToastMessage("Paciente registrado y asociado al tutor exitosamente");

      // Log exitoso en Sentry
      Sentry.withScope((scope) => {
        scope.setTag("accion", "registro_paciente");
        scope.setTag("paciente", formData.nombre);
        scope.setTag("tutor_rut", formData.rut_tutor);
        scope.setLevel("info");
        Sentry.captureMessage("Paciente registrado exitosamente");
      });

      // Limpiar formulario
      setFormData({
        nombre: "",
        especie: null,
        raza: null,
        color: "",
        sexo: "",
        fechaNacimiento: "",
        esterilizado: false,
        codigo_chip: "",
        rut_tutor: "",
      });
      setEspecieQuery("");
      setRazaQuery("");
    } catch (error) {
      console.error("❌ Error registrando paciente:", error);
      setToastMessage(
        "Error al registrar paciente. Revisa los datos e intenta de nuevo."
      );

      // Log de error en Sentry
      Sentry.withScope((scope) => {
        scope.setTag("accion", "registro_paciente");
        scope.setTag("paciente", formData.nombre);
        scope.setTag("tutor_rut", formData.rut_tutor);
        scope.setLevel("error");
        Sentry.captureException(error);
      });
    }
    setShowToast(true);
  };

  const handleTutorRegistrado = (tutor: any) => {
    //console.log("✅ Tutor registrado y seleccionado:", tutor);
    setFormData((prev) => ({
      ...prev,
      rut_tutor: tutor.rut,
    }));
  };

  return {
    formData,
    setFormData,
    especiesData,
    razasData,
    loadingEspecies,
    loadingRazas,
    initialLoading,
    especieQuery,
    razaQuery,
    showEspecieList,
    showRazaList,
    showToast,
    toastMessage,
    setEspecieQuery,
    setRazaQuery,
    setShowEspecieList,
    setShowRazaList,
    setShowToast,
    handleInputChange,
    selectEspecie,
    selectRaza,
    registraPaciente,
    clearEspecie,
    handleTutorRegistrado,
  };
};
