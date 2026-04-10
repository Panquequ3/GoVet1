import React from "react";
import {
  IonItem,
  IonLabel,
  IonIcon,
  IonButton,
  IonButtons,
} from "@ionic/react";
import {
  personOutline,
  pencilOutline,
  personSharp,
  idCardOutline,
  mailOutline,
  locationOutline,
} from "ionicons/icons";
import { TutorData } from "../../api/tutores";
// Componente: Visualizador de información de tutor
interface TutorItemProps {
  tutor: TutorData;
  onView: () => void;
  onEdit: () => void;
  disabled: boolean;
}
import "../../styles/ver.css";

const TutorItem: React.FC<TutorItemProps> = ({
  tutor,
  onView,
  onEdit,
  disabled,
}) => {
  return (
    <IonItem
      lines="none"
      className="tutor-item"
      button
      onClick={onView}
      disabled={disabled}
      id={`tutor-item-${tutor.rut}`}
    >
      <IonIcon icon={personSharp} slot="start" className="item-icon" />
      <IonLabel style={{ padding: "5px" }}>
        <h2 className="tutor-nombre">
          {tutor.nombre} {tutor.apellido_paterno} {tutor.apellido_materno}
        </h2>
        <div>
          <h2>
            <p>
              <IonIcon src="/id.svg" className="pacientes-icon" />
              <span style={{ marginLeft: "8px" }}>: {tutor.rut}</span>
            </p>
          </h2>
        </div>
        {tutor.direccion && (
          <div>
            <h2>
              <p>
                <IonIcon icon={locationOutline} className="pacientes-icon" />
                <span style={{ marginLeft: "8px" }}>: {tutor.direccion}</span>
              </p>
            </h2>
          </div>
        )}
        {tutor.email && (
          <div>
            <h2>
              <p>
                <IonIcon icon={mailOutline} className="pacientes-icon" />
                <span style={{ marginLeft: "8px" }}>: {tutor.email}</span>
              </p>
            </h2>
          </div>
        )}
      </IonLabel>
      <IonButtons slot="end">
        <IonButton
          fill="clear"
          id={`edit-tutor-${tutor.rut}`}
          onClick={(e) => {
            e.stopPropagation();
            onEdit();
          }}
          disabled={disabled}
        >
          <IonIcon
            className="icon"
            icon={pencilOutline}
            slot="icon-only"
            size="small"
          />
        </IonButton>
      </IonButtons>
    </IonItem>
  );
};

export default TutorItem;
