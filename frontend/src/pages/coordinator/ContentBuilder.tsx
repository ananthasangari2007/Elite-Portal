import { useState, useEffect } from "react";
import { ChevronDown, ChevronUp, Edit2, File, FileText, Link as LinkIcon, Lock, Plus, Trash2, Unlock, Video, Upload } from "lucide-react";
import { api } from "../../lib/api";
import { useApi } from "../../lib/hooks";
import { formatBytes, humanize } from "../../lib/format";
import { Card, EmptyState, Field, Modal, PageHeader, PageLoader, StatusBadge } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";

export default function ContentBuilder() {
  const { push } = useToast();
  const { data: domains } = useApi<any[]>("/coordinator/domains");
  const [domainId, setDomainId] = useState<string>("");
  const [days, setDays] = useState<any[]>([]);
  const [loadingDays, setLoadingDays] = useState(false);
  const [showDayModal, setShowDayModal] = useState(false);
  const [editingDay, setEditingDay] = useState<any>(null);
  const [dayForm, setDayForm] = useState({ title: "", description: "", learning_objectives: "" });
  const [expanded, setExpanded] = useState<number | null>(null);
  const [materials, setMaterials] = useState<any[]>([]);
  const [showMatModal, setShowMatModal] = useState(false);
  const [matForm, setMatForm] = useState({
    title: "", material_type: "video", description: "", url: "", file: null as File | null,
    duration_minutes: "", display_order: "", tags: ""
  });

  useEffect(() => {
    if (domains?.length && !domainId) setDomainId(String(domains[0].id));
  }, [domains]);

  useEffect(() => {
    if (!domainId) return;
    loadDays();
  }, [domainId]);

  async function loadDays() {
    setLoadingDays(true);
    try {
      const res = await api.get<any>(`/coordinator/domains/${domainId}/days`);
      setDays(res.days || []);
    } finally {
      setLoadingDays(false);
    }
  }

  async function saveDay() {
    try {
      if (editingDay) {
        await api.patch(`/coordinator/days/${editingDay.id}`, dayForm);
      } else {
        await api.post(`/coordinator/domains/${domainId}/days`, dayForm);
      }
      setShowDayModal(false);
      setEditingDay(null);
      setDayForm({ title: "", description: "", learning_objectives: "" });
      loadDays();
      push("Day saved", "success");
    } catch (e: any) {
      push(e.message, "error");
    }
  }

  async function publishDay(id: number) {
    try {
      await api.post(`/coordinator/days/${id}/publish`);
      loadDays();
      push("Day published", "success");
    } catch (e: any) {
      push(e.message, "error");
    }
  }

  async function lockDay(id: number, locked: boolean) {
    try {
      await api.post(`/coordinator/days/${id}/lock`, { locked });
      loadDays();
      push(locked ? "Day locked" : "Day unlocked", "success");
    } catch (e: any) {
      push(e.message, "error");
    }
  }

  async function deleteDay(id: number) {
    if (!confirm("Delete this day?")) return;
    try {
      await api.del(`/coordinator/days/${id}`);
      loadDays();
      push("Day deleted", "success");
    } catch (e: any) {
      push(e.message, "error");
    }
  }

  async function reorder(id: number, dir: "up" | "down") {
    const idx = days.findIndex((d) => d.id === id);
    if (idx < 0) return;
    const newOrder = [...days].map((d) => d.id);
    const swap = dir === "up" ? idx - 1 : idx + 1;
    if (swap < 0 || swap >= newOrder.length) return;
    [newOrder[idx], newOrder[swap]] = [newOrder[swap], newOrder[idx]];
    try {
      await api.post(`/coordinator/days/reorder`, { domain_id: Number(domainId), ordered_ids: newOrder });
      loadDays();
    } catch (e: any) {
      push(e.message, "error");
    }
  }

  async function loadMaterials(dayId: number) {
    setExpanded(dayId);
    try {
      const res = await api.get<any>(`/coordinator/days/${dayId}/materials`);
      setMaterials(res.materials || []);
    } catch (e) {
      setMaterials([]);
    }
  }

  async function saveMaterial(dayId: number) {
    try {
      let payload: any = { ...matForm, day_id: dayId };
      if (matForm.file) {
        const fd = new FormData();
        fd.append("file", matForm.file);
        fd.append("folder", "materials");
        const up = await api.upload<any>("/uploads", fd);
        payload = {
          ...payload,
          file_key: up.file_key || up.key,
          file_name: up.file_name,
          file_size: up.file_size,
          url: up.url || up.preview_url || payload.url,
        };
      }
      await api.post(`/coordinator/days/${dayId}/materials`, payload);
      setShowMatModal(false);
      setMatForm({ title: "", material_type: "video", description: "", url: "", file: null, duration_minutes: "", display_order: "", tags: "" });
      loadMaterials(dayId);
      push("Material added", "success");
    } catch (e: any) {
      push(e.message, "error");
    }
  }

  async function deleteMaterial(id: number, dayId: number) {
    if (!confirm("Delete material?")) return;
    try {
      await api.del(`/coordinator/materials/${id}`);
      loadMaterials(dayId);
      push("Material deleted", "success");
    } catch (e: any) {
      push(e.message, "error");
    }
  }

  function openEditDay(d: any) {
    setEditingDay(d);
    setDayForm({ title: d.title, description: d.description || "", learning_objectives: d.learning_objectives || "" });
    setShowDayModal(true);
  }

  return (
    <div>
      <PageHeader
        title="Content Builder"
        subtitle="Create and manage learning days and materials"
        actions={
          <button className="btn-primary" onClick={() => { setEditingDay(null); setDayForm({ title: "", description: "", learning_objectives: "" }); setShowDayModal(true); }}>
            <Plus className="h-4 w-4" /> New Day
          </button>
        }
      />

      <Card className="mb-4">
        <Field label="Select Domain">
          <select className="input" value={domainId} onChange={(e) => setDomainId(e.target.value)}>
            {domains?.map((d) => (
              <option key={d.id} value={d.id}>{d.name}</option>
            ))}
          </select>
        </Field>
      </Card>

      {loadingDays ? (
        <PageLoader />
      ) : !days.length ? (
        <Card><EmptyState title="No days yet" description="Create the first learning day for this domain" /></Card>
      ) : (
        <div className="space-y-3">
          {days.map((d, idx) => (
            <Card key={d.id} pad={false}>
              <div className="flex items-center justify-between px-5 py-4">
                <div className="flex items-center gap-3">
                  <button className="btn-ghost !px-1.5" onClick={() => (expanded === d.id ? setExpanded(null) : loadMaterials(d.id))}>
                    {expanded === d.id ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                  </button>
                  <div>
                    <p className="text-sm font-medium text-slate-800">Day {d.day_number}: {d.title}</p>
                    <p className="text-xs text-slate-500">{d.material_count} materials · {d.assessment_count} assessments</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge status={d.status} />
                  <button className="btn-secondary !px-2.5 !py-1.5" onClick={() => reorder(d.id, "up")} disabled={idx === 0}>↑</button>
                  <button className="btn-secondary !px-2.5 !py-1.5" onClick={() => reorder(d.id, "down")} disabled={idx === days.length - 1}>↓</button>
                  <button className="btn-secondary !px-2.5 !py-1.5" onClick={() => openEditDay(d)}><Edit2 className="h-4 w-4" /></button>
                  <button className="btn-secondary !px-2.5 !py-1.5" onClick={() => lockDay(d.id, !d.is_locked)}>{d.is_locked ? <Unlock className="h-4 w-4" /> : <Lock className="h-4 w-4" />}</button>
                  {d.status !== "published" && <button className="btn-primary !px-2.5 !py-1.5" onClick={() => publishDay(d.id)}>Publish</button>}
                  <button className="btn-danger !px-2.5 !py-1.5" onClick={() => deleteDay(d.id)}><Trash2 className="h-4 w-4" /></button>
                </div>
              </div>
              {expanded === d.id && (
                <div className="border-t border-slate-100 px-5 py-4">
                  <div className="mb-3 flex items-center justify-between">
                    <p className="text-sm font-semibold text-slate-800">Materials</p>
                    <button className="btn-primary !px-2.5 !py-1.5" onClick={() => { setShowMatModal(true); }}><Plus className="h-3.5 w-3.5" /> Add Material</button>
                  </div>
                  {!materials.length ? (
                    <EmptyState title="No materials" />
                  ) : (
                    <div className="space-y-2">
                      {materials.map((m: any) => (
                        <div key={m.id} className="flex items-center justify-between rounded-xl border border-slate-200 p-3">
                          <div className="flex items-center gap-3">
                            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-100 text-slate-500">
                              {m.material_type === "video" ? <Video className="h-4 w-4" /> : m.material_type === "pdf" ? <FileText className="h-4 w-4" /> : m.material_type === "link" ? <LinkIcon className="h-4 w-4" /> : <File className="h-4 w-4" />}
                            </div>
                            <div>
                              <p className="text-sm font-medium text-slate-800">{m.title}</p>
                              <p className="text-xs text-slate-500">{humanize(m.material_type)} {m.file_size ? "· " + formatBytes(m.file_size) : ""} {m.url ? "· " + m.url : ""}</p>
                            </div>
                          </div>
                          <button className="btn-danger !px-2.5 !py-1.5" onClick={() => deleteMaterial(m.id, d.id)}><Trash2 className="h-4 w-4" /></button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      <Modal open={showDayModal} onClose={() => setShowDayModal(false)} title={editingDay ? "Edit Day" : "New Day"} footer={
        <>
          <button className="btn-secondary" onClick={() => setShowDayModal(false)}>Cancel</button>
          <button className="btn-primary" onClick={saveDay}>Save</button>
        </>
      }>
        <div className="space-y-3">
          <Field label="Title"><input className="input" value={dayForm.title} onChange={(e) => setDayForm({ ...dayForm, title: e.target.value })} /></Field>
          <Field label="Description"><textarea className="input min-h-[80px]" value={dayForm.description} onChange={(e) => setDayForm({ ...dayForm, description: e.target.value })} /></Field>
          <Field label="Learning Objectives"><textarea className="input min-h-[80px]" value={dayForm.learning_objectives} onChange={(e) => setDayForm({ ...dayForm, learning_objectives: e.target.value })} /></Field>
        </div>
      </Modal>

      <Modal open={showMatModal} onClose={() => setShowMatModal(false)} title="Add Material" footer={
        <>
          <button className="btn-secondary" onClick={() => setShowMatModal(false)}>Cancel</button>
          <button className="btn-primary" onClick={() => expanded && saveMaterial(expanded)}>Save</button>
        </>
      }>
        <div className="space-y-3">
          <Field label="Type">
            <select className="input" value={matForm.material_type} onChange={(e) => setMatForm({ ...matForm, material_type: e.target.value })}>
              <option value="video">Video</option>
              <option value="article">Article</option>
              <option value="pdf">PDF</option>
              <option value="link">Link</option>
              <option value="slide">Slide</option>
            </select>
          </Field>
          <Field label="Title"><input className="input" value={matForm.title} onChange={(e) => setMatForm({ ...matForm, title: e.target.value })} /></Field>
          <Field label="URL"><input className="input" value={matForm.url} onChange={(e) => setMatForm({ ...matForm, url: e.target.value })} placeholder="Or upload file below" /></Field>
          <Field label="Upload File">
            <input type="file" className="input" onChange={(e) => setMatForm({ ...matForm, file: e.target.files?.[0] || null })} />
            {matForm.file && <p className="mt-1 text-xs text-slate-500">{matForm.file.name} · {formatBytes(matForm.file.size)}</p>}
          </Field>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Duration (min)"><input type="number" className="input" value={matForm.duration_minutes} onChange={(e) => setMatForm({ ...matForm, duration_minutes: e.target.value })} /></Field>
            <Field label="Display Order"><input type="number" className="input" value={matForm.display_order} onChange={(e) => setMatForm({ ...matForm, display_order: e.target.value })} /></Field>
          </div>
          <Field label="Description"><textarea className="input min-h-[60px]" value={matForm.description} onChange={(e) => setMatForm({ ...matForm, description: e.target.value })} /></Field>
          <Field label="Tags"><input className="input" value={matForm.tags} onChange={(e) => setMatForm({ ...matForm, tags: e.target.value })} /></Field>
        </div>
      </Modal>
    </div>
  );
}