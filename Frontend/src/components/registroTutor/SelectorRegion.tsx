import React, { useRef, useEffect } from "react";
import {
  IonItem,
  IonInput,
  IonList,
  IonLabel,
  IonSpinner,
  IonText,
  IonIcon,
} from "@ionic/react";
import { chevronDownOutline, locationOutline } from "ionicons/icons";
import { formatRegionName } from "../../utils/formatters";
// Componente: Gestor de tutores
interface SelectorRegionProps {
  regionQuery: string;
  setRegionQuery: (query: string) => void;
  showRegionList: boolean;
  setShowRegionList: (show: boolean) => void;
  filteredRegiones: any[];
  loadingRegiones: boolean;
  selectRegion: (id: string, nombre: string, fullRegion: any) => void;
}

export const SelectorRegion: React.FC<SelectorRegionProps> = ({
  regionQuery,
  setRegionQuery,
  showRegionList,
  setShowRegionList,
  filteredRegiones,
  loadingRegiones,
  selectRegion,
}) => {
  const wrapperRef = useRef<HTMLDivElement>(null);

  // Debug: mostrar estado del componente
  useEffect(() => {
    /*console.log("📋 SelectorRegion estado:", {
      showRegionList,
      filteredRegionesCount: filteredRegiones.length,
      loadingRegiones,
      regionQuery,
    });*/
  }, [showRegionList, filteredRegiones, loadingRegiones, regionQuery]);

  // Cerrar dropdown al hacer click fuera
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        wrapperRef.current &&
        !wrapperRef.current.contains(event.target as Node)
      ) {
        setShowRegionList(false);
      }
    };

    if (showRegionList) {
      document.addEventListener("mousedown", handleClickOutside);
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [showRegionList, setShowRegionList]);

  return (
    <div ref={wrapperRef} style={{ position: "relative", width: "100%" }}>
      <IonItem lines="none" className="searchbar-container">
        <IonInput
          id="region_id"
          labelPlacement="stacked"
          fill="outline"
          placeholder="Buscar región..."
          value={regionQuery}
          onIonInput={(e) => {
            setRegionQuery(e.detail.value!);
            setShowRegionList(true);
          }}
          onIonFocus={() => setShowRegionList(true)}
        >
          <div slot="label">
            Región <IonText color="danger">(*)</IonText>
          </div>
        </IonInput>
        <IonIcon
          icon={chevronDownOutline}
          slot="end"
          style={{
            marginTop: "1.5rem",
            color: "var(--ion-color-medium)",
            pointerEvents: "none",
          }}
        />
      </IonItem>

      {showRegionList && (
        <div
          style={{
            position: "absolute",
            top: "100%",
            left: 0,
            right: 0,
            zIndex: 9999,
            backgroundColor: "white",
            boxShadow: "0 4px 6px rgba(0, 0, 0, 0.1)",
            borderRadius: "8px",
            marginTop: "4px",
            border: "1px solid var(--ion-color-light-shade)",
            maxHeight: "240px",
            overflowY: "auto",
          }}
        >
          {loadingRegiones ? (
            <div style={{ padding: "1rem", textAlign: "center" }}>
              <IonSpinner name="dots" />
              <div
                style={{
                  marginTop: "0.5rem",
                  color: "var(--ion-color-medium)",
                }}
              >
                Cargando regiones...
              </div>
            </div>
          ) : filteredRegiones.length > 0 ? (
            <IonList style={{ padding: 0, margin: 0 }}>
              {filteredRegiones.map((region) => {
                const formattedName = formatRegionName(region);
                return (
                  <IonItem
                    id="region_option"
                    key={region.id}
                    button
                    onClick={() =>
                      selectRegion(region.id, formattedName, region)
                    }
                    style={{
                      "--padding-start": "12px",
                      "--inner-padding-end": "12px",
                      cursor: "pointer",
                    }}
                  >
                    <IonIcon
                      icon={locationOutline}
                      slot="start"
                      style={{
                        color: "var(--ion-color-primary)",
                        opacity: 0.6,
                      }}
                    />
                    <IonLabel>{formattedName}</IonLabel>
                  </IonItem>
                );
              })}
            </IonList>
          ) : (
            <div
              style={{
                padding: "1rem",
                textAlign: "center",
                color: "var(--ion-color-medium)",
                fontSize: "0.9rem",
              }}
            >
              No se encontraron regiones con "{regionQuery}"
            </div>
          )}
        </div>
      )}
    </div>
  );
};
