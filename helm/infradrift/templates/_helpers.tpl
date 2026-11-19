{{/*
Expand the name of the chart.
*/}}
{{- define "infradrift.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "infradrift.fullname" -}}
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
Create chart name and version as used by the chart label.
*/}}
{{- define "infradrift.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "infradrift.labels" -}}
helm.sh/chart: {{ include "infradrift.chart" . }}
app.kubernetes.io/name: {{ include "infradrift.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- with .Values.commonLabels }}
{{ toYaml . }}
{{- end }}
{{- end }}

{{/*
Secret name
*/}}
{{- define "infradrift.secretName" -}}
{{- if .Values.secrets.existingSecret }}
{{- .Values.secrets.existingSecret }}
{{- else }}
{{- printf "%s-secrets" (include "infradrift.fullname" .) }}
{{- end }}
{{- end }}

{{/*
PostgreSQL Service Name
*/}}
{{- define "infradrift.postgresHost" -}}
{{- printf "%s-postgres" (include "infradrift.fullname" .) }}
{{- end }}

{{/*
Database URL construction
*/}}
{{- define "infradrift.databaseUrl" -}}
{{- if .Values.secrets.databaseUrl }}
{{- .Values.secrets.databaseUrl }}
{{- else }}
{{- printf "postgresql+psycopg://%s:%s@%s:%d/%s" .Values.postgresql.auth.username (.Values.secrets.postgresPassword | default .Values.postgresql.auth.password) (include "infradrift.postgresHost" .) (int .Values.postgresql.service.port) .Values.postgresql.auth.database }}
{{- end }}
{{- end }}
