import React from "react";
import { IonSegment, IonSegmentButton, IonLabel, IonIcon } from "@ionic/react";
import { personOutline, pawOutline, documentTextOutline } from "ionicons/icons";
import SearchBar from "./SearchBar";
import "../../styles/SegmentedView.css";

interface SegmentedViewProps {
  selectedSegment: string;
  onSegmentChange: (segment: string) => void;
  busqueda: string;
  onSearch: (texto: string) => void;
  children: React.ReactNode;
}

const SegmentedView: React.FC<SegmentedViewProps> = ({
  selectedSegment,
  onSegmentChange,
  busqueda,
  onSearch,
  children,
}) => {
  return (
    <>
      <div className="segment-container-sticky">
        <IonSegment
          value={selectedSegment}
          onIonChange={(e) => onSegmentChange(e.detail.value as string)}
        >
          <IonSegmentButton id = "boton_busqueda_tutores" value="tutores">
            <IonIcon icon={personOutline} />
            <IonLabel id = "header_tutores_busqueda">Tutores</IonLabel>
          </IonSegmentButton>
          <IonSegmentButton value="pacientes">
            <IonIcon icon={pawOutline} />
            <IonLabel>Pacientes</IonLabel>
          </IonSegmentButton>
          <IonSegmentButton value="consultas">
            <IonIcon icon={documentTextOutline} />
            <IonLabel>Consultas</IonLabel>
          </IonSegmentButton>
        </IonSegment>
        <SearchBar
          id="Barra_Busqueda"
          value={busqueda}
          onSearch={onSearch}
          placeholder={
            selectedSegment === "tutores"
              ? "Buscar por nombre, apellido, RUT o email..."
              : selectedSegment === "pacientes"
              ? "Buscar por nombre, raza o especie..."
              : "Buscar por nombre de paciente o tutor..."
          }
          className="searchbar"
        />
      </div>
      {children}
    </>
  );
};

export default SegmentedView;
