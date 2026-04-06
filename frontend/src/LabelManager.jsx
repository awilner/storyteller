import { useI18n } from "./I18nContext";
import { fetchLabels, createLabel, updateLabel, deleteLabel } from "./api";
import MetadataListManager from "./MetadataListManager";

export default function LabelManager({ projectId, onClose, embedded }) {
  const t = useI18n();
  return (
    <MetadataListManager
      projectId={projectId} embedded={embedded} onClose={onClose} t={t}
      title={t("labels.title")} addLabel={t("labels.add")} defaultName={t("labels.name")}
      deleteWarningKey="labels.delete_warning"
      fetchItems={fetchLabels} createItem={createLabel} updateItem={updateLabel} deleteItem={deleteLabel}
    />
  );
}
