const fail = message => Object.assign(new Error(message), {status: 409});
export function installationContextView(value) {
  const keys = ['api_compatibility_version','schema_version','source_commit','status'];
  if (!value || Array.isArray(value) || Object.keys(value).sort().join() !== keys.join() ||
      value.schema_version !== 1 || !['recorded','unrecorded'].includes(value.status) ||
      typeof value.api_compatibility_version !== 'string' ||
      !/^[a-zA-Z0-9][a-zA-Z0-9._+-]{0,63}$/.test(value.api_compatibility_version) ||
      (value.status === 'recorded' ? typeof value.source_commit !== 'string' ||
        !/^[a-f0-9]{40}$/.test(value.source_commit) : value.source_commit !== null))
    throw fail('Der Installationsnachweis ist unvollständig. Bitte neu laden.');
  return {source: value.source_commit, compatibility: value.api_compatibility_version,
    recorded: value.status === 'recorded'};
}

export async function readInstallationContext(api, {current = () => true} = {}) {
  const generation = api.generation;
  const check = caps => {
    if (!current() || api.generation !== generation ||
        !caps?.permissions?.includes('settings.manage') ||
        !caps?.features?.includes('installation_context'))
      throw Object.assign(new Error('Die aktuelle Freigabe für den Serverstand fehlt.'), {status: 403});
  };
  check(await api.get('/business/capabilities'));
  const value = installationContextView(await api.get('/business/installation'));
  check(await api.get('/business/capabilities'));
  return value;
}
