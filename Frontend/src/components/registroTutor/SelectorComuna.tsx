import React from "react";
import {
  IonItem,
  IonInput,
  IonList,
  IonLabel,
  IonSpinner,
  IonText,
} from "@ionic/react";
import { formatComunaName } from "../../utils/formatters";
// Componente: Gestor de tutores
interface SelectorComunaProps {
  comunaQuery: string;
  setComunaQuery: (query: string) => void;
  showComunaList: boolean;
  setShowComunaList: (show: boolean) => void;
  filteredComunas: any[];
  loadingComunas: boolean;
  selectComuna: (id: string, nombre: string) => void;
  regionSeleccionada: boolean;
}

export const SelectorComuna: React.FC<SelectorComunaProps> = ({
  comunaQuery,
  setComunaQuery,
  showComunaList,
  setShowComunaList,
  filteredComunas,
  loadingComunas,
  selectComuna,
  regionSeleccionada,
}) => {
  return (
    <>
      <IonItem lines="none" className="searchbar-container">
        <IonInput
          id = "comuna_id"
          labelPlacement="stacked"
          fill="outline"
          placeholder={
            regionSeleccionada
              ? "Buscar comuna..."
              : "Primero selecciona una región"
          }
          value={comunaQuery}
          disabled={!regionSeleccionada}
          onIonInput={(e) => {
            if (regionSeleccionada) {
              setComunaQuery(e.detail.value!);
              setShowComunaList(true);
            }
          }}
          onIonFocus={() => {
            if (regionSeleccionada) {
              setShowComunaList(true);
            }
          }}
          onIonBlur={() => {
            // Pequeño delay para permitir que el click en la lista se registre
            setTimeout(() => {
              setShowComunaList(false);
            }, 150);
          }}
        >
          <div slot="label">
            Comuna <IonText color="danger">(*)</IonText>
          </div>
        </IonInput>
      </IonItem>
      {showComunaList && regionSeleccionada && filteredComunas.length > 0 && (
        <IonList className="filter-list">
          {loadingComunas ? (
            <IonItem>
              <IonSpinner />
              <IonLabel>Cargando comunas...</IonLabel>
            </IonItem>
          ) : (
            filteredComunas.map((comuna: any, index: number) => {
              const formattedName = formatComunaName(comuna.name);
              return (
                <IonItem
                  id = "comuna_option"
                  key={`${comuna.id || index}`}
                  button
                  onClick={() =>
                    selectComuna(comuna.id || index.toString(), formattedName)
                  }
                >
                  <IonLabel>{formattedName}</IonLabel>
                </IonItem>
              );
            })
          )}
        </IonList>
      )}
    </>
  );
};
