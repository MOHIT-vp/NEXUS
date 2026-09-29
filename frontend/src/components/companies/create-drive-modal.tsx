"use client";

import { useState } from "react";
import { X, Building2, Plus, Loader2 } from "lucide-react";
import { PBButton } from "@/components/ui/pb-button";
import { PBBadge } from "@/components/ui/pb-badge";
import { createRecruitmentDrive, JobDrive } from "@/lib/api";

interface CreateDriveModalProps {
  isOpen: boolean;
  onClose: () => void;
  onDriveCreated: (drive: JobDrive) => void;
}

export function CreateDriveModal({ isOpen, onClose, onDriveCreated }: CreateDriveModalProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form states
  const [companyName, setCompanyName] = useState("");
  const [industry, setIndustry] = useState("Technology");
  const [website, setWebsite] = useState("");
  const [location, setLocation] = useState("Bengaluru, India (Hybrid)");
  const [roleTitle, setRoleTitle] = useState("");
  const [roleFamily, setRoleFamily] = useState("software_engineering");
  const [packageLpa, setPackageLpa] = useState<number>(14.0);
  const [minCgpa, setMinCgpa] = useState<number>(7.0);
  const [maxBacklogs, setMaxBacklogs] = useState<number>(0);
  const [minExperience, setMinExperience] = useState<number>(0);
  const [driveDate, setDriveDate] = useState("2026-11-15");
  const [deadline, setDeadline] = useState("2026-11-01");
  const [status, setStatus] = useState("upcoming");
  const [description, setDescription] = useState("");

  // Skills input
  const [reqSkillInput, setReqSkillInput] = useState("");
  const [requiredSkills, setRequiredSkills] = useState<string[]>(["Python", "SQL", "Data Structures"]);
  const [prefSkillInput, setPrefSkillInput] = useState("");
  const [preferredSkills, setPreferredSkills] = useState<string[]>(["Docker", "AWS"]);

  // Rounds
  const [rounds, setRounds] = useState([
    { round_number: 1, name: "Online Coding Assessment", type: "coding_test", description: "DSA and problem solving", duration_minutes: 90 },
    { round_number: 2, name: "Technical Interview", type: "technical_interview", description: "Core CS, projects, and architecture", duration_minutes: 60 },
    { round_number: 3, name: "HR & Culture Round", type: "hr", description: "Values alignment and behavioral fit", duration_minutes: 30 },
  ]);

  if (!isOpen) return null;

  const handleAddReqSkill = () => {
    if (reqSkillInput.trim() && !requiredSkills.includes(reqSkillInput.trim())) {
      setRequiredSkills([...requiredSkills, reqSkillInput.trim()]);
      setReqSkillInput("");
    }
  };

  const handleRemoveReqSkill = (skill: string) => {
    setRequiredSkills(requiredSkills.filter(s => s !== skill));
  };

  const handleAddPrefSkill = () => {
    if (prefSkillInput.trim() && !preferredSkills.includes(prefSkillInput.trim())) {
      setPreferredSkills([...preferredSkills, prefSkillInput.trim()]);
      setPrefSkillInput("");
    }
  };

  const handleRemovePrefSkill = (skill: string) => {
    setPreferredSkills(preferredSkills.filter(s => s !== skill));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!companyName.trim() || !roleTitle.trim()) {
      setError("Company Name and Role Title are required.");
      return;
    }
    if (packageLpa <= 0) {
      setError("Package must be greater than 0 LPA.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const payload = {
        name: companyName.trim(),
        industry: industry.trim(),
        website: website.trim() || undefined,
        location: location.trim(),
        description: description.trim() || `Recruitment drive for ${roleTitle} at ${companyName}.`,
        role_title: roleTitle.trim(),
        role_family: roleFamily,
        package_lpa: packageLpa,
        min_cgpa: minCgpa,
        max_backlogs: maxBacklogs,
        min_experience: minExperience,
        required_skills: requiredSkills,
        preferred_skills: preferredSkills,
        drive_date: driveDate,
        deadline: deadline,
        status: status,
        selection_rounds: rounds,
      };

      const created = await createRecruitmentDrive(payload);
      onDriveCreated(created);
      onClose();
    } catch (err: unknown) {
      console.error("Failed to list company:", err);
      const msg = err instanceof Error ? err.message : "Failed to list recruitment drive. Please try again.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-charcoal/50 backdrop-blur-sm animate-fade-in overflow-y-auto">
      <div className="surface-card bg-ivory w-full max-w-2xl rounded-2xl shadow-xl border border-border-default my-8 flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="p-6 border-b border-border-subtle flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-orange/10 flex items-center justify-center text-orange">
              <Building2 className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-charcoal font-zodiak">List New Recruitment Drive</h2>
              <p className="text-xs text-bronze-dark/50">Post a new visiting company and specify eligibility & skill criteria.</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-surface-muted text-bronze-dark/50 hover:text-charcoal transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 overflow-y-auto space-y-6 flex-1">
          {error && (
            <div className="p-3 bg-danger-light text-danger text-sm rounded-lg border border-danger/20 font-medium">
              {error}
            </div>
          )}

          {/* Section 1: Company Profile */}
          <div className="space-y-4">
            <h3 className="type-micro text-bronze-dark/70">1. COMPANY INFORMATION</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-charcoal mb-1">Company Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Google India, Goldman Sachs"
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  className="w-full px-3 py-2 text-sm bg-surface border border-border-default rounded-lg focus:outline-none focus:border-orange"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-charcoal mb-1">Industry</label>
                <input
                  type="text"
                  placeholder="e.g. Fintech, Enterprise Cloud, AI"
                  value={industry}
                  onChange={(e) => setIndustry(e.target.value)}
                  className="w-full px-3 py-2 text-sm bg-surface border border-border-default rounded-lg focus:outline-none focus:border-orange"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-charcoal mb-1">Website URL</label>
                <input
                  type="url"
                  placeholder="https://company.com"
                  value={website}
                  onChange={(e) => setWebsite(e.target.value)}
                  className="w-full px-3 py-2 text-sm bg-surface border border-border-default rounded-lg focus:outline-none focus:border-orange"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-charcoal mb-1">Work Location</label>
                <input
                  type="text"
                  placeholder="e.g. Bengaluru, Hyderabad, Remote"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  className="w-full px-3 py-2 text-sm bg-surface border border-border-default rounded-lg focus:outline-none focus:border-orange"
                />
              </div>
            </div>
          </div>

          {/* Section 2: Role & Criteria */}
          <div className="space-y-4">
            <h3 className="type-micro text-bronze-dark/70">2. JOB ROLE & ELIGIBILITY</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-charcoal mb-1">Role Title *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Software Development Engineer I"
                  value={roleTitle}
                  onChange={(e) => setRoleTitle(e.target.value)}
                  className="w-full px-3 py-2 text-sm bg-surface border border-border-default rounded-lg focus:outline-none focus:border-orange"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-charcoal mb-1">Role Domain</label>
                <select
                  value={roleFamily}
                  onChange={(e) => setRoleFamily(e.target.value)}
                  className="w-full px-3 py-2 text-sm bg-surface border border-border-default rounded-lg focus:outline-none focus:border-orange"
                >
                  <option value="software_engineering">Software Engineering</option>
                  <option value="data_engineering">Data Engineering</option>
                  <option value="devops">DevOps & Cloud</option>
                  <option value="analytics">Data Analytics</option>
                  <option value="core">Core Engineering</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-charcoal mb-1">Annual Package (₹ LPA) *</label>
                <input
                  type="number"
                  step="0.5"
                  min="1"
                  required
                  value={packageLpa}
                  onChange={(e) => setPackageLpa(parseFloat(e.target.value) || 0)}
                  className="w-full px-3 py-2 text-sm bg-surface border border-border-default rounded-lg focus:outline-none focus:border-orange"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-charcoal mb-1">Minimum CGPA Cutoff</label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="10"
                  value={minCgpa}
                  onChange={(e) => setMinCgpa(parseFloat(e.target.value) || 0)}
                  className="w-full px-3 py-2 text-sm bg-surface border border-border-default rounded-lg focus:outline-none focus:border-orange"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-charcoal mb-1">Max Active Backlogs</label>
                <input
                  type="number"
                  min="0"
                  max="10"
                  value={maxBacklogs}
                  onChange={(e) => setMaxBacklogs(parseInt(e.target.value) || 0)}
                  className="w-full px-3 py-2 text-sm bg-surface border border-border-default rounded-lg focus:outline-none focus:border-orange"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-charcoal mb-1">Drive Date</label>
                <input
                  type="date"
                  value={driveDate}
                  onChange={(e) => setDriveDate(e.target.value)}
                  className="w-full px-3 py-2 text-sm bg-surface border border-border-default rounded-lg focus:outline-none focus:border-orange"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-charcoal mb-1">Application Deadline</label>
                <input
                  type="date"
                  value={deadline}
                  onChange={(e) => setDeadline(e.target.value)}
                  className="w-full px-3 py-2 text-sm bg-surface border border-border-default rounded-lg focus:outline-none focus:border-orange"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs font-semibold text-charcoal mb-1">Job Description & Responsibilities</label>
              <textarea
                rows={2}
                placeholder="Overview of the position, team, and day-to-day work..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full px-3 py-2 text-sm bg-surface border border-border-default rounded-lg focus:outline-none focus:border-orange"
              />
            </div>
          </div>

          {/* Section 3: Required & Preferred Skills */}
          <div className="space-y-4">
            <h3 className="type-micro text-bronze-dark/70">3. REQUIRED & PREFERRED SKILLS</h3>
            
            {/* Required Skills */}
            <div>
              <label className="block text-xs font-semibold text-charcoal mb-1">
                Mandatory Required Skills (Evaluated with high weight)
              </label>
              <div className="flex gap-2 mb-2">
                <input
                  type="text"
                  placeholder="e.g. Python, Docker, SQL"
                  value={reqSkillInput}
                  onChange={(e) => setReqSkillInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); handleAddReqSkill(); } }}
                  className="flex-1 px-3 py-1.5 text-sm bg-surface border border-border-default rounded-lg focus:outline-none focus:border-orange"
                />
                <button
                  type="button"
                  onClick={handleAddReqSkill}
                  className="px-3 py-1.5 text-xs font-semibold bg-surface-muted hover:bg-orange/10 hover:text-orange text-charcoal rounded-lg transition-colors flex items-center gap-1"
                >
                  <Plus className="w-3.5 h-3.5" /> Add
                </button>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {requiredSkills.map(skill => (
                  <span
                    key={skill}
                    className="inline-flex items-center gap-1 text-xs px-2.5 py-1 bg-orange/10 text-orange border border-orange/20 rounded-md font-medium"
                  >
                    {skill}
                    <button
                      type="button"
                      onClick={() => handleRemoveReqSkill(skill)}
                      className="hover:text-danger ml-0.5"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
                {requiredSkills.length === 0 && (
                  <span className="text-xs text-bronze-dark/40 italic">No required skills added yet.</span>
                )}
              </div>
            </div>

            {/* Preferred Skills */}
            <div>
              <label className="block text-xs font-semibold text-charcoal mb-1">
                Preferred / Nice-to-Have Skills (Bonus points in matching)
              </label>
              <div className="flex gap-2 mb-2">
                <input
                  type="text"
                  placeholder="e.g. AWS, Kubernetes, Redis"
                  value={prefSkillInput}
                  onChange={(e) => setPrefSkillInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); handleAddPrefSkill(); } }}
                  className="flex-1 px-3 py-1.5 text-sm bg-surface border border-border-default rounded-lg focus:outline-none focus:border-orange"
                />
                <button
                  type="button"
                  onClick={handleAddPrefSkill}
                  className="px-3 py-1.5 text-xs font-semibold bg-surface-muted hover:bg-orange/10 hover:text-orange text-charcoal rounded-lg transition-colors flex items-center gap-1"
                >
                  <Plus className="w-3.5 h-3.5" /> Add
                </button>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {preferredSkills.map(skill => (
                  <span
                    key={skill}
                    className="inline-flex items-center gap-1 text-xs px-2.5 py-1 bg-surface border border-border-default text-charcoal rounded-md font-medium"
                  >
                    {skill}
                    <button
                      type="button"
                      onClick={() => handleRemovePrefSkill(skill)}
                      className="hover:text-danger ml-0.5"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Section 4: Selection Process Rounds */}
          <div className="space-y-3">
            <h3 className="type-micro text-bronze-dark/70">4. SELECTION PROCESS & INTERVIEW ROUNDS</h3>
            <div className="space-y-2">
              {rounds.map((r, i) => (
                <div key={i} className="p-3 bg-surface border border-border-subtle rounded-lg flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-surface-muted font-bold flex items-center justify-center text-bronze-dark">
                      {r.round_number}
                    </span>
                    <div>
                      <p className="font-semibold text-charcoal">{r.name}</p>
                      <p className="text-bronze-dark/50">{r.description} · {r.duration_minutes} mins</p>
                    </div>
                  </div>
                  <PBBadge variant="medium">{r.type.replace("_", " ")}</PBBadge>
                </div>
              ))}
            </div>
          </div>
        </form>

        {/* Footer */}
        <div className="p-5 border-t border-border-subtle flex items-center justify-end gap-3 bg-surface-warm/50 rounded-b-2xl">
          <PBButton variant="secondary" onClick={onClose} disabled={loading}>
            Cancel
          </PBButton>
          <PBButton variant="primary" onClick={handleSubmit} disabled={loading} className="min-w-[140px]">
            {loading ? (
              <span className="flex items-center gap-1.5">
                <Loader2 className="w-4 h-4 animate-spin" /> Publishing...
              </span>
            ) : (
              "Publish Drive"
            )}
          </PBButton>
        </div>
      </div>
    </div>
  );
}
