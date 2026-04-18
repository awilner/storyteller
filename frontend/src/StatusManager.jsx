import { useI18n } from "./I18nContext";
import { fetchStatuses, createStatus, updateStatus, deleteStatus } from "./api";
import MetadataListManager from "./MetadataListManager";

export default function StatusManager({ projectId, onClose, embedded, readOnly }) {
  const t = useI18n();
  return (
    <MetadataListManager
      projectId={projectId} embedded={embedded} onClose={onClose} t={t}
      title={t("statuses.title")} addLabel={t("statuses.add")} defaultName={t("statuses.name")}
      deleteWarningKey="statuses.delete_warning"
      fetchItems={fetchStatuses} createItem={createStatus} updateItem={updateStatus} deleteItem={deleteStatus}
      readOnly={readOnly}
    />
  );
}
