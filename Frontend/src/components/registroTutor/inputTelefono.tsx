import {
  useState,
  useRef,
  useEffect,
  forwardRef,
  useImperativeHandle,
} from "react";
import { IonInput, IonItem, IonText } from "@ionic/react";

import { MaskitoOptions, maskitoTransform } from "@maskito/core";
import { useMaskito } from "@maskito/react";

import "../../styles/registroTutor.css";

interface InputTelefonoProps {
  onPhoneChange: (phone: string) => void;
  initialValue?: string; // nuevo prop para valor inicial
}

export interface InputTelefonoHandle {
  reset: () => void; // método que el padre podrá llamar
  setValue: (value: string) => void; // nuevo método para establecer valor
}

const InputTelefono = forwardRef<InputTelefonoHandle, InputTelefonoProps>(
  ({ onPhoneChange, initialValue }, ref) => {
    const phoneMaskOptions: MaskitoOptions = {
      mask: [
        "+",
        "5",
        "6",
        " ",
        "9",
        " ",
        /\d/,
        /\d/,
        /\d/,
        /\d/,
        " ",
        /\d/,
        /\d/,
        /\d/,
        /\d/,
      ],
    };
    const phoneMask = useMaskito({ options: phoneMaskOptions });

    const formatPhoneWithMask = (phone: string) => {
      if (!phone || phone.trim() === "") {
        return maskitoTransform("569 ", phoneMaskOptions);
      }
      // Limpiar el número de cualquier formato previo
      const cleanPhone = phone.replace(/\D/g, "");
      // Agregar el prefijo 56 si no lo tiene
      const withPrefix = cleanPhone.startsWith("56")
        ? cleanPhone
        : "56" + cleanPhone;
      return maskitoTransform(withPrefix, phoneMaskOptions);
    };

    const [myPhoneNumber, setMyPhoneNumber] = useState(
      formatPhoneWithMask(initialValue || "")
    );

    const phoneInputRef = useRef<HTMLIonInputElement | null>(null);

    useEffect(() => {
      if (phoneInputRef.current) {
        phoneInputRef.current.getInputElement().then((input) => {
          phoneMask(input);
        });
      }
    }, [phoneMask]);

    // Exponemos métodos al padre
    useImperativeHandle(ref, () => ({
      reset() {
        const defaultValue = maskitoTransform("569 ", phoneMaskOptions);
        setMyPhoneNumber(defaultValue);
        onPhoneChange(""); // limpiamos el valor en el padre
      },
      setValue(value: string) {
        const formatted = formatPhoneWithMask(value);
        setMyPhoneNumber(formatted);
        const cleaned = formatted.replace("+56", "").replace(/\s/g, "");
        onPhoneChange(cleaned);
      },
    }));

    // Efecto para actualizar cuando cambia initialValue
    useEffect(() => {
      if (initialValue !== undefined) {
        const formatted = formatPhoneWithMask(initialValue);
        setMyPhoneNumber(formatted);
      }
    }, [initialValue]);

    const handleInput = (e: CustomEvent) => {
      const value = e.detail.value || "";
      setMyPhoneNumber(value);

      // Eliminar el prefijo "+56" y espacios antes de enviar al padre
      const cleaned = value.replace("+56", "").replace(/\s/g, "");
      onPhoneChange(cleaned);
    };

    return (
      <IonItem>
        <IonInput
          id="id_telefono"
          type="tel"
          labelPlacement="stacked"
          fill="outline"
          name="celular"
          ref={phoneInputRef}
          value={myPhoneNumber}
          onIonInput={handleInput}
          placeholder="+56 9 "
        >
          <div slot="label">
            Celular <IonText color="danger">(*)</IonText>
          </div>
        </IonInput>
      </IonItem>
    );
  }
);

export default InputTelefono;
