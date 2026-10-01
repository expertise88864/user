/* Settings draft state machine. Cloud saves never mean production publication.
 * The UI supplies the fixed font choices and paints cloned state snapshots.
 * Requests use the existing same-origin cookie; no credential is persisted. */
(function () {
  'use strict';
  const SHA = /^(?!0{40}$)[a-f0-9]{40}$/;
  const KEY = 'cd_site_settings_local_v2';
  const clone = value => value === null ? null : JSON.parse(JSON.stringify(value));
  const canonical = value => Array.isArray(value) ? value.map(canonical) : value && typeof value === 'object' ?
    Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])])) : value;
  const equal = (a, b) => JSON.stringify(canonical(a)) === JSON.stringify(canonical(b));
  const error = code => Object.assign(new Error(code), {code});

  function create({auth, fonts, storage, fetch: request, changed = () => {}}) {
    const choices = clone(fonts);
    let loaded = null, working = null, remote = null, loadedIdentity = null, remoteIdentity = null;
    let editRevision = 0, busy = false, uncertain = false, needsRefresh = false, status = 'not_loaded', publicationObservation = null;
    function snapshot() {
      return clone({loaded, working, remote, editRevision, busy, uncertain, needsRefresh, status,
        publication: !!loaded && current(loadedIdentity) ? publicationObservation : null, authorised: !!loaded && current(loadedIdentity),
        dirty: !!working && (!loaded || !equal(working, loaded.settings))});
    }
    function emit(next) { if (next) status = next; changed(snapshot()); }
    function identity() { return {pat: auth.getPat(), revision: auth.getRevision()}; }
    function current(identity) { return !!identity.pat && auth.getPat() === identity.pat && auth.getRevision() === identity.revision; }
    function validSettings(value, articles, stored = false) {
      if (!value || value.version !== 1 || typeof value.legacyPicks !== 'boolean' || Object.keys(value).sort().join(',') !== 'font,legacyPicks,order,picks,version' ||
          !value.font || Object.keys(value.font).sort().join(',') !== Object.keys(choices).sort().join(',')) throw error('invalid_settings');
      for (const [key, values] of Object.entries(choices)) if (!values.includes(value.font[key])) throw error('invalid_settings');
      const slugs = new Set(articles.map(article => article.slug));
      for (const [key, max] of [['order', 200], ['picks', 12]]) {
        const values = value[key];
        if (!Array.isArray(values) || values.length > max || new Set(values).size !== values.length || values.some(slug =>
          typeof slug !== 'string' || slug.length > 100 || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug) || (!stored && !slugs.has(slug)))) throw error('invalid_settings');
      }
      if (!value.picks.length || (!stored && value.order.length && value.order.length !== articles.length)) throw error('invalid_settings');
      return clone(value);
    }
    function validResponse(value) {
      if (!value || !['main', 'blobSha', 'baseSha', 'catalogSha', 'mainBlobSha', 'mainCatalogSha'].every(key => SHA.test(value[key] || '')) ||
          !(value.head === null || SHA.test(value.head || '')) || typeof value.conflict !== 'boolean' ||
          value.published !== false || value.deploymentVerified !== false || !Array.isArray(value.articles) ||
          !value.articles.length || value.articles.length > 200 || new Set(value.articles.map(item => item.slug)).size !== value.articles.length ||
          value.articles.some(item => !item || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(item.slug) ||
            ['title', 'title_en'].some(key => typeof item[key] !== 'string' || !item[key].trim() || item[key].length > 500))) throw error('invalid_settings_response');
      if (value.sourceRequiresReview !== undefined && typeof value.sourceRequiresReview !== 'boolean') throw error('invalid_settings_response');
      validSettings(value.sourceSettings, value.articles, value.sourceRequiresReview === true);
      validSettings(value.settings, value.articles, value.conflict);
      const expected = value.conflict ? 'conflict' : value.request ? 'requested' : value.head ? 'cloud_draft' : 'source_base';
      if (value.status !== expected) throw error('invalid_settings_response');
      return clone(value);
    }
    async function http(input, observing = false) {
      const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 25_000);
      try {
        const response = await request('/api/admin/site-settings' + (observing ? '?publication=1' : ''), {method: input ? 'POST' : 'GET', credentials: 'same-origin', cache: 'no-store',
          redirect: 'error', signal: controller.signal, ...(input ? {headers: {'Content-Type': 'application/json'}, body: JSON.stringify(input)} : {})});
        const reader = response.body?.getReader();
        if (!reader) throw error('invalid_settings_response');
        const chunks = []; let length = 0;
        try {
          for (;;) {
            const {done, value} = await reader.read(); if (done) break;
            length += value.byteLength; if (length > 384_000) throw error('invalid_settings_response'); chunks.push(value);
          }
        } finally { await reader.cancel(); }
        const bytes = new Uint8Array(length); let offset = 0;
        for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
        let value;
        try { value = JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(bytes)); } catch (_) { throw error('invalid_settings_response'); }
        if (!response.ok) {
          const knownGate = response.status === 409 && ['settings_receipt_not_retired','settings_publication_not_verified'].includes(value.error);
          throw Object.assign(error(knownGate ? value.error : response.status === 409 ? 'settings_conflict' : response.status === 401 ? 'login_required' : 'settings_request_failed'), {status: response.status});
        }
        return validResponse(value);
      } finally { clearTimeout(timer); }
    }
    function set(kind, values) {
      if (!loaded || loaded.conflict || !['font', 'order', 'picks'].includes(kind)) throw error('settings_not_ready');
      working = validSettings({...working, [kind]: clone(values), ...(kind === 'picks' ? {legacyPicks: false} : {})}, loaded.articles);
      publicationObservation = null; editRevision++; emit('local_changes'); return snapshot();
    }
    function saveLocal() {
      if (!working || !loaded) throw error('settings_not_ready');
      const value = {version: 2, head: loaded.head, baseSha: loaded.baseSha, catalogSha: loaded.catalogSha, settings: clone(working), savedAt: Date.now()};
      try { storage.setItem(KEY, JSON.stringify(value)); emit('local_saved'); return true; }
      catch (_) { emit('local_storage_failed'); return false; }
    }
    function recoverLocal() {
      if (busy || !loaded || loaded.conflict) throw error('settings_not_ready');
      let value;
      try { value = JSON.parse(storage.getItem(KEY)); } catch (_) { emit('local_recovery_invalid'); return false; }
      if (!value) return false;
      if (value.version !== 2 || value.head !== loaded.head || value.baseSha !== loaded.baseSha || value.catalogSha !== loaded.catalogSha) {
        emit('local_recovery_conflict'); return false;
      }
      try { working = validSettings(value.settings, loaded.articles); } catch (_) { emit('local_recovery_invalid'); return false; }
      publicationObservation = null; editRevision++; emit('local_recovered'); return true;
    }
    function adoptRemote(expectedRevision) {
      if (busy || !remote || expectedRevision !== editRevision) throw error('settings_changed');
      if (!current(remoteIdentity)) throw error('login_changed');
      // The caller obtains explicit author confirmation before using this.
      loaded = remote; loadedIdentity = remoteIdentity; remote = null; remoteIdentity = null;
      working = loaded.conflict ? null : clone(loaded.settings);
      publicationObservation = null; uncertain = false; needsRefresh = false; editRevision++; emit(loaded.conflict ? 'settings_conflict' : 'remote_loaded');
      return snapshot();
    }
    async function operation(input) {
      if (busy) throw error('settings_busy');
      const started = identity(); if (!started.pat) throw error('login_required');
      const revision = editRevision, before = clone(loaded);
      const submitted = input?.kind ? {...before.settings, [input.kind]: clone(working[input.kind]),
        ...(input.kind === 'picks' ? {legacyPicks: false} : {})} : clone(working);
      publicationObservation = null; busy = true; emit(input ? 'saving_cloud' : 'loading_cloud');
      try {
        const result = await http(input);
        if (!current(started)) { loaded = null; remote = null; loadedIdentity = null; remoteIdentity = null; throw error('login_changed'); }
        if (input) {
          if (result.verified !== true || !result.head || result.head === before.head || result.conflict ||
              result.baseSha !== before.baseSha || result.catalogSha !== before.catalogSha ||
              !equal(result.settings, submitted) || result.published !== false) throw error('settings_write_not_verified');
          const intent = input.action === 'request-publication', cancel = input.action === 'cancel-request';
          if ((intent && (result.request?.draftHead !== before.head || result.request?.requestHead !== result.head || result.request?.blobSha !== before.blobSha)) ||
              (!intent && result.request !== null) || ((intent || cancel) && result.blobSha !== before.blobSha)) throw error('settings_write_not_verified');
          loaded = result; loadedIdentity = started; remote = null; remoteIdentity = null; uncertain = false; needsRefresh = false;
          // Keep typing and unsaved values of the other two kinds. The exact
          // saved snapshot advances the cloud base, never replaces local edits.
          emit(editRevision !== revision || !equal(working, result.settings) ? 'cloud_saved_newer_local_changes' : intent ? 'requested' : 'cloud_saved');
        } else if (uncertain || needsRefresh || editRevision !== revision || (!!working && (!before || !equal(working, before.settings)))) {
          remote = result; remoteIdentity = started; emit('compare_required');
        } else {
          loaded = result; loadedIdentity = started; remote = null; remoteIdentity = null; working = result.conflict ? null : clone(result.settings);
          emit(result.conflict ? 'settings_conflict' : 'remote_loaded');
        }
        return snapshot();
      } catch (caught) {
        if (caught.code === 'settings_conflict') needsRefresh = true;
        if (input && (!caught.status || caught.status >= 500) && caught.code !== 'login_changed') uncertain = true;
        emit(caught.code === 'login_changed' ? 'login_changed' : caught.code === 'settings_conflict' ? 'settings_conflict' :
          uncertain ? 'write_unconfirmed' : caught.code === 'login_required' ? 'login_required' : 'request_failed');
        // Keep working/recovery data and sanitise all provider details.
        throw error(status);
      } finally { busy = false; emit(); }
    }
    function writable() {
      if (!loaded || !working || loaded.conflict || remote || uncertain || needsRefresh) throw error('settings_not_ready');
      if (!current(loadedIdentity)) throw error('login_changed');
    }
    function saveCloud(kind) {
      writable(); if (!['font', 'order', 'picks'].includes(kind)) throw error('invalid_settings_kind');
      // Other unsaved kinds must remain local after this partial save.
      const values = clone(working[kind]);
      // Clicking save on the initial list is itself an explicit choice. Keep
      // that migration in the local snapshot even if transport is uncertain.
      if (kind === 'picks' && working.legacyPicks) set(kind, values);
      const pending = operation({expectedHead: loaded.head, baseSha: loaded.baseSha, catalogSha: loaded.catalogSha, kind, values});
      return pending;
    }
    function publication(approved) {
      writable(); if (approved !== true || !loaded.head || !equal(working, loaded.settings)) throw error('settings_approval_required');
      return operation({action: 'request-publication', expectedHead: loaded.head, blobSha: loaded.blobSha,
        baseSha: loaded.baseSha, catalogSha: loaded.catalogSha, settingsApproved: true});
    }
    function cancelRequest() {
      writable(); if (!loaded.request || !equal(working, loaded.settings)) throw error('settings_not_ready');
      return operation({action: 'cancel-request', expectedHead: loaded.head, blobSha: loaded.blobSha, baseSha: loaded.baseSha, catalogSha: loaded.catalogSha});
    }
    async function observe() {
      if (busy || !loaded || remote || uncertain || needsRefresh || snapshot().dirty) throw error('settings_not_ready');
      const started = identity(), before = loaded, revision = editRevision;
      if (!current(loadedIdentity)) throw error('login_changed');
      publicationObservation = null; busy = true; emit('checking_publication');
      try {
        const result = await http(null, true), proof = result.publication;
        if (!current(started)) throw error('login_changed');
        if (loaded !== before || editRevision !== revision || result.head !== before.head || result.blobSha !== before.blobSha ||
            result.baseSha !== before.baseSha || result.catalogSha !== before.catalogSha || !equal(result.settings, before.settings)) throw error('publication_changed');
        const states = ['unverified', 'changed', 'not_published', 'ci_missing', 'ci_running', 'ci_failed',
          'deployment_missing', 'deployment_failed', 'deployment_running', 'live'];
        if (!proof || proof.kind !== 'site-settings' || !states.includes(proof.state) ||
            proof.loadedHead !== before.head || proof.loadedBlobSha !== before.blobSha || proof.mainSha !== result.main ||
            proof.mainBlobSha !== result.mainBlobSha || proof.settingsValidated !== true ||
            !Number.isFinite(Date.parse(proof.observedAt)) || !Array.isArray(proof.checks) ||
            ['ciVerified','deploymentVerified','published','matchesLoadedVersion'].some(key => typeof proof[key] !== 'boolean') ||
            proof.matchesLoadedVersion !== (proof.mainBlobSha === before.blobSha) ||
            proof.deploymentVerified !== (proof.state === 'live') ||
            proof.published !== (proof.state === 'live' && proof.matchesLoadedVersion) ||
            (proof.state === 'live' && (!proof.ciVerified || !Number.isSafeInteger(proof.deploymentId) || proof.deploymentId <= 0)) ||
            (['ci_missing','ci_running','ci_failed','changed','not_published'].includes(proof.state) && proof.ciVerified)) throw error('publication_unavailable');
        publicationObservation = clone({...proof,sourceSettings:result.sourceSettings,articles:result.articles,mainCatalogSha:result.mainCatalogSha});
        emit('publication_observed'); return snapshot();
      } catch (caught) {
        publicationObservation = null;
        emit(['login_changed','publication_changed'].includes(caught.code) ? caught.code : 'publication_unavailable');
        throw error(status);
      } finally { busy = false; emit(); }
    }
    async function newVersion(confirmed, expectedRevision) {
      if (busy || !loaded?.head || remote || uncertain || needsRefresh || snapshot().dirty || expectedRevision !== editRevision) throw error('settings_not_ready');
      if (!current(loadedIdentity)) throw error('login_changed');
      const proof = clone(publicationObservation);
      if (confirmed !== true || proof?.state !== 'live' || !proof.ciVerified || !proof.deploymentVerified ||
          proof.loadedHead !== loaded.head || proof.loadedBlobSha !== loaded.blobSha || !SHA.test(proof.mainCatalogSha || '')) throw error('settings_confirmation_required');
      const before = loaded, started = identity(), revision = editRevision;
      const source = validSettings(proof.sourceSettings, proof.articles);
      const input = {action:'new-version',expectedHead:before.head,blobSha:before.blobSha,expectedMain:proof.mainSha,
        expectedMainBlob:proof.mainBlobSha,expectedCatalog:proof.mainCatalogSha,confirmed:true};
      publicationObservation = null; busy = true; emit('creating_new_version');
      try {
        const result = await http(input);
        if (!current(started)) throw error('login_changed');
        if (loaded !== before || result.verified !== true || !result.head || result.head === before.head || result.conflict || result.request !== null ||
            result.main !== input.expectedMain || result.mainBlobSha !== input.expectedMainBlob || result.blobSha !== input.expectedMainBlob ||
            result.baseSha !== input.expectedMainBlob || result.catalogSha !== input.expectedCatalog || result.mainCatalogSha !== input.expectedCatalog ||
            result.manifestRecord?.baseMain !== input.expectedMain || !equal(result.settings, source) || !equal(result.sourceSettings, source)) throw error('settings_new_version_not_verified');
        const nextWorking = clone(result.settings);
        // Adoption was explicit; only typing after submission overrides the
        // newly selected baseline. Preserve each changed kind independently.
        if (editRevision !== revision && working) {
          for (const kind of ['font','order','picks']) if (!equal(working[kind], before.settings[kind])) nextWorking[kind] = clone(working[kind]);
          if (working.legacyPicks !== before.settings.legacyPicks) nextWorking.legacyPicks = working.legacyPicks;
        }
        try { validSettings(nextWorking, result.articles); }
        catch (_) {
          // A newer catalogue can invalidate typing done while creating the
          // cycle. Keep the old loaded/editable snapshot and offer comparison.
          remote = result; remoteIdentity = started; needsRefresh = true; uncertain = false;
          emit('compare_required'); return snapshot();
        }
        loaded = result; loadedIdentity = started; working = nextWorking; remote = null; remoteIdentity = null;
        uncertain = false; needsRefresh = false;
        emit(editRevision !== revision ? 'new_version_newer_local_changes' : 'new_version_created'); return snapshot();
      } catch (caught) {
        if (['settings_conflict','login_changed'].includes(caught.code)) needsRefresh = true;
        if ((!caught.status || caught.status >= 500) && caught.code !== 'login_changed') uncertain = true;
        emit(caught.code === 'login_changed' ? 'login_changed' : caught.code === 'settings_conflict' ? 'settings_conflict' :
          uncertain ? 'write_unconfirmed' : ['settings_receipt_not_retired','settings_publication_not_verified'].includes(caught.code) ? caught.code : 'new_version_failed');
        throw error(status);
      } finally { busy = false; emit(); }
    }
    function catalogPlan(base = 'draft') {
      if (!loaded?.conflict || !['draft','source'].includes(base) || !(loaded.sourceRequiresReview || loaded.catalogSha !== loaded.mainCatalogSha)) throw error('settings_not_ready');
      const original = validSettings(base === 'source' ? loaded.sourceSettings : loaded.settings, loaded.articles, true);
      const current = loaded.articles.map(item => item.slug), visible = new Set(current), settings = clone(original);
      const removed = [...new Set(original.order.concat(original.picks))].filter(slug => !visible.has(slug));
      const added = original.order.length ? current.filter(slug => !original.order.includes(slug)) : [];
      if (settings.order.length) settings.order = settings.order.filter(slug => visible.has(slug)).concat(added);
      settings.picks = settings.picks.filter(slug => visible.has(slug));
      if (!loaded.settings.legacyPicks || !loaded.sourceSettings.legacyPicks || removed.some(slug => original.picks.includes(slug))) settings.legacyPicks = false;
      return clone({settings, original, removed, added});
    }
    async function reconcileCatalog(settings, confirmed, expectedRevision) {
      if (busy || !loaded?.conflict || remote || uncertain || needsRefresh || snapshot().dirty || expectedRevision !== editRevision) throw error('settings_not_ready');
      catalogPlan(); // Only catalogue conflicts can use this action.
      if (confirmed !== true) throw error('settings_confirmation_required');
      if (!current(loadedIdentity)) throw error('login_changed');
      const selected = validSettings(settings,loaded.articles), before = loaded, started = identity();
      if ((!before.settings.legacyPicks || !before.sourceSettings.legacyPicks) && selected.legacyPicks) throw error('invalid_settings');
      const input = {action:'reconcile-catalog',expectedHead:before.head,blobSha:before.blobSha,expectedMain:before.main,
        expectedMainBlob:before.mainBlobSha,expectedCatalog:before.mainCatalogSha,settings:selected,confirmed:true};
      publicationObservation = null; busy = true; emit('reconciling_catalog');
      try {
        const result = await http(input);
        if (!current(started)) throw error('login_changed');
        if (loaded !== before || editRevision !== expectedRevision || result.verified !== true || !result.head || result.head === before.head ||
            result.main !== before.main || result.mainBlobSha !== before.mainBlobSha || result.blobSha === before.blobSha && !equal(selected,before.settings) ||
            result.baseSha !== before.mainBlobSha || result.catalogSha !== before.mainCatalogSha || result.mainCatalogSha !== before.mainCatalogSha ||
            result.manifestRecord?.baseMain !== before.main || result.conflict || result.request !== null || !equal(result.settings,selected)) throw error('settings_reconciliation_not_verified');
        loaded = result; loadedIdentity = started; working = clone(result.settings); remote = null; remoteIdentity = null;
        editRevision++; uncertain = false; needsRefresh = false; emit('catalog_reconciled'); return snapshot();
      } catch (caught) {
        if (['settings_conflict','login_changed'].includes(caught.code)) needsRefresh = true;
        if ((!caught.status || caught.status >= 500) && caught.code !== 'login_changed') uncertain = true;
        emit(caught.code === 'login_changed' ? 'login_changed' : caught.code === 'settings_conflict' ? 'settings_conflict' :
          uncertain ? 'write_unconfirmed' : caught.code === 'settings_receipt_not_retired' ? caught.code : 'request_failed');
        throw error(status);
      } finally { busy = false; emit(); }
    }
    return {snapshot, set, saveLocal, recoverLocal, adoptRemote, load: () => operation(), saveCloud, publication, cancelRequest, observe, newVersion, catalogPlan, reconcileCatalog};
  }
  window.CDSettingsDrafts = {create};
})();
