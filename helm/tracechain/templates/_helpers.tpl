{{/*
Expand the name of the chart.
*/}}
{{- define "tracechain.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "tracechain.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Chart label (name + version).
*/}}
{{- define "tracechain.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels applied to every resource.
*/}}
{{- define "tracechain.labels" -}}
helm.sh/chart: {{ include "tracechain.chart" . }}
{{ include "tracechain.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels shared by all components.
*/}}
{{- define "tracechain.selectorLabels" -}}
app.kubernetes.io/name: {{ include "tracechain.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Backend component labels.
*/}}
{{- define "tracechain.backend.labels" -}}
{{ include "tracechain.labels" . }}
app.kubernetes.io/component: backend
{{- end }}

{{- define "tracechain.backend.selectorLabels" -}}
{{ include "tracechain.selectorLabels" . }}
app.kubernetes.io/component: backend
{{- end }}

{{/*
Dashboard component labels.
*/}}
{{- define "tracechain.dashboard.labels" -}}
{{ include "tracechain.labels" . }}
app.kubernetes.io/component: dashboard
{{- end }}

{{- define "tracechain.dashboard.selectorLabels" -}}
{{ include "tracechain.selectorLabels" . }}
app.kubernetes.io/component: dashboard
{{- end }}

{{/*
Name of the Secret used by the backend.
Returns values.secrets.existingSecret when set, otherwise the chart-managed secret.
*/}}
{{- define "tracechain.secretName" -}}
{{- if .Values.secrets.existingSecret }}
{{- .Values.secrets.existingSecret }}
{{- else }}
{{- printf "%s-secrets" (include "tracechain.fullname" .) }}
{{- end }}
{{- end }}

{{/*
Database URL used by the backend.
Derived from database.type + database.external.url or database.sqlite.path.
*/}}
{{- define "tracechain.databaseUrl" -}}
{{- if eq .Values.database.type "external" }}
{{- .Values.database.external.url }}
{{- else }}
{{- printf "sqlite:///%s" .Values.database.sqlite.path }}
{{- end }}
{{- end }}

{{/*
Effective NEXT_PUBLIC_API_URL for the dashboard.
Defaults to http://<fullname>-backend:<port>.
*/}}
{{- define "tracechain.apiUrl" -}}
{{- if .Values.dashboard.apiUrl }}
{{- .Values.dashboard.apiUrl }}
{{- else }}
{{- printf "http://%s-backend:%d" (include "tracechain.fullname" .) (int .Values.backend.service.port) }}
{{- end }}
{{- end }}
