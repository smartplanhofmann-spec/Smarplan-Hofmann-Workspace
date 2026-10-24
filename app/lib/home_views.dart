import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'api.dart';
import 'app_version.dart';
import 'design.dart';

class LoginView extends StatefulWidget {
  final TextEditingController email, password;
  final GlobalKey<FormState> formKey;
  final bool busy;
  final String? error;
  final VoidCallback onLogin;
  final VoidCallback? onOffline;
  final String? connectionLabel;
  const LoginView({
    super.key,
    required this.email,
    required this.password,
    required this.formKey,
    required this.busy,
    this.error,
    required this.onLogin,
    this.onOffline,
    this.connectionLabel,
  });
  @override
  State<LoginView> createState() => _LoginViewState();
}

class _LoginViewState extends State<LoginView> {
  bool visible = false;
  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: LayoutBuilder(
        builder: (context, box) {
          final wide = box.maxWidth >= 950;
          final inset = wide ? 56.0 : 24.0;
          return SingleChildScrollView(
            child: ConstrainedBox(
              constraints: BoxConstraints(minHeight: box.maxHeight),
              child: Padding(
                padding: EdgeInsets.all(inset),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Row(
                      children: [
                        PlanMark(),
                        SizedBox(width: 12),
                        Text(
                          'smartplan',
                          style: TextStyle(
                            fontSize: 23,
                            fontWeight: FontWeight.w600,
                            letterSpacing: -.9,
                          ),
                        ),
                        SizedBox(width: 8),
                        Text(
                          'office',
                          style: TextStyle(
                            fontSize: 23,
                            fontWeight: FontWeight.w400,
                            letterSpacing: -.9,
                            color: OfficeColors.muted,
                          ),
                        ),
                      ],
                    ),
                    SizedBox(height: wide ? 76 : 44),
                    Center(
                      child: ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 1120),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.center,
                          children: [
                            if (wide)
                              Expanded(
                                child: Padding(
                                  padding: const EdgeInsets.only(right: 64),
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      const Eyebrow('Raum für gute Arbeit'),
                                      const SizedBox(height: 24),
                                      const Text(
                                        'Weniger suchen.',
                                        style: TextStyle(
                                          fontSize: 52,
                                          height: 1.14,
                                          letterSpacing: -2.7,
                                          fontWeight: FontWeight.w600,
                                        ),
                                      ),
                                      const Text(
                                        'Mehr schaffen.',
                                        style: TextStyle(
                                          fontSize: 52,
                                          height: 1.14,
                                          letterSpacing: -2.7,
                                          fontWeight: FontWeight.w600,
                                          color: OfficeColors.blue,
                                        ),
                                      ),
                                      const SizedBox(height: 24),
                                      const Text(
                                        'Projekte, Berichte und Ihr Team.\nAlles an einem klaren Ort.',
                                        style: TextStyle(
                                          fontSize: 17,
                                          height: 1.75,
                                          color: OfficeColors.muted,
                                        ),
                                      ),
                                      const SizedBox(height: 40),
                                      const SizedBox(
                                        height: 155,
                                        width: 400,
                                        child: CustomPaint(
                                          painter: _PlanIllustration(),
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                            Expanded(
                              child: Align(
                                alignment: wide
                                    ? Alignment.centerRight
                                    : Alignment.center,
                                child: ConstrainedBox(
                                  constraints: const BoxConstraints(
                                    maxWidth: 410,
                                  ),
                                  child: OfficeSurface(
                                    padding: EdgeInsets.all(wide ? 36 : 24),
                                    child: Form(
                                      key: widget.formKey,
                                      child: AutofillGroup(
                                        child: Column(
                                          crossAxisAlignment:
                                              CrossAxisAlignment.stretch,
                                          children: [
                                            const Eyebrow('Ihr Arbeitsbereich'),
                                            if (widget.connectionLabel !=
                                                null) ...[
                                              const SizedBox(height: 10),
                                              Text(
                                                widget.connectionLabel!,
                                                style: const TextStyle(
                                                  fontSize: 12,
                                                  color: OfficeColors.muted,
                                                ),
                                              ),
                                            ],
                                            const SizedBox(height: 15),
                                            Text(
                                              'Willkommen\nzurück.',
                                              style: Theme.of(context)
                                                  .textTheme
                                                  .headlineLarge,
                                            ),
                                            const SizedBox(height: 12),
                                            const Text(
                                              'Melden Sie sich bei Smartplan Office an.',
                                              style: TextStyle(
                                                color: OfficeColors.muted,
                                                fontSize: 13,
                                              ),
                                            ),
                                            const SizedBox(height: 28),
                                            if (widget.error != null)
                                              Notice(widget.error!),
                                            TextFormField(
                                              controller: widget.email,
                                              keyboardType:
                                                  TextInputType.emailAddress,
                                              textInputAction:
                                                  TextInputAction.next,
                                              autofillHints: const [
                                                AutofillHints.username,
                                              ],
                                              decoration: const InputDecoration(
                                                labelText: 'E-Mail',
                                              ),
                                              validator: (v) =>
                                                  (v ?? '').trim().isEmpty
                                                  ? 'E-Mail eingeben.'
                                                  : null,
                                            ),
                                            const SizedBox(height: 16),
                                            TextFormField(
                                              controller: widget.password,
                                              obscureText: !visible,
                                              autocorrect: false,
                                              enableSuggestions: false,
                                              autofillHints: const [
                                                AutofillHints.password,
                                              ],
                                              onFieldSubmitted: (_) {
                                                if (!widget.busy)
                                                  widget.onLogin();
                                              },
                                              decoration: InputDecoration(
                                                labelText: 'Passwort',
                                                suffixIcon: IconButton(
                                                  tooltip: visible
                                                      ? 'Passwort verbergen'
                                                      : 'Passwort anzeigen',
                                                  onPressed: () => setState(
                                                    () => visible = !visible,
                                                  ),
                                                  icon: Icon(
                                                    visible
                                                        ? Icons
                                                              .visibility_off_outlined
                                                        : Icons
                                                              .visibility_outlined,
                                                    size: 19,
                                                  ),
                                                ),
                                              ),
                                              validator: (v) =>
                                                  (v ?? '').isEmpty
                                                  ? 'Passwort eingeben.'
                                                  : null,
                                            ),
                                            const SizedBox(height: 24),
                                            FilledButton(
                                              onPressed: widget.busy
                                                  ? null
                                                  : widget.onLogin,
                                              child: Row(
                                                mainAxisAlignment:
                                                    MainAxisAlignment.center,
                                                children: [
                                                  if (widget.busy) ...[
                                                    const SizedBox(
                                                      width: 16,
                                                      height: 16,
                                                      child:
                                                          CircularProgressIndicator(
                                                            strokeWidth: 2,
                                                          ),
                                                    ),
                                                    const SizedBox(width: 10),
                                                  ],
                                                  const Text('Anmelden'),
                                                  const SizedBox(width: 12),
                                                  const Icon(
                                                    Icons.arrow_forward_rounded,
                                                    size: 17,
                                                  ),
                                                ],
                                              ),
                                            ),
                                            if (widget.onOffline != null)
                                              TextButton.icon(
                                                onPressed: widget.busy
                                                    ? null
                                                    : widget.onOffline,
                                                icon: const Icon(
                                                  Icons.offline_pin_outlined,
                                                ),
                                                label: const Text(
                                                  'Offline-Pläne entsperren',
                                                ),
                                              ),
                                            const SizedBox(height: 22),
                                            const Row(
                                              mainAxisAlignment:
                                                  MainAxisAlignment.center,
                                              children: [
                                                Icon(
                                                  Icons.lock_outline_rounded,
                                                  size: 13,
                                                  color: OfficeColors.muted,
                                                ),
                                                SizedBox(width: 6),
                                                Flexible(
                                                  child: Text(
                                                    'Ihr Zugang. Ihre Projekte.',
                                                    style: TextStyle(
                                                      fontSize: 11,
                                                      color: OfficeColors.muted,
                                                    ),
                                                  ),
                                                ),
                                              ],
                                            ),
                                          ],
                                        ),
                                      ),
                                    ),
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    SizedBox(height: wide ? 60 : 36),
                    const Center(
                      child: Text(
                        'SMARTPLAN HOFMANN  ·  MIT ÜBERBLICK ANS WERK.',
                        style: TextStyle(
                          fontSize: 9,
                          letterSpacing: 1.3,
                          color: OfficeColors.muted,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    ),
  );
}

class _PlanIllustration extends CustomPainter {
  const _PlanIllustration();
  @override
  void paint(Canvas canvas, Size size) {
    canvas.save();
    canvas.translate(12, 18);
    final w = math.min(size.width - 24, 360.0);
    final thin = Paint()
      ..color = const Color(0xffdedee4)
      ..strokeWidth = 1
      ..style = PaintingStyle.stroke;
    for (var x = 0.0; x < w; x += 20) {
      canvas.drawLine(
        Offset(x, 0),
        Offset(x, 118),
        thin..color = const Color(0xffe9e9ee),
      );
    }
    for (var y = 0.0; y < 120; y += 20) {
      canvas.drawLine(Offset(0, y), Offset(w, y), thin);
    }
    final p = Paint()
      ..color = const Color(0xffa4a4ae)
      ..strokeWidth = 1.5
      ..style = PaintingStyle.stroke;
    final plan = Path()
      ..moveTo(24, 94)
      ..lineTo(24, 16)
      ..lineTo(w - 32, 16)
      ..lineTo(w - 32, 94)
      ..lineTo(w * .65, 94)
      ..moveTo(w * .5, 94)
      ..lineTo(24, 94)
      ..moveTo(w * .36, 16)
      ..lineTo(w * .36, 58)
      ..lineTo(24, 58)
      ..moveTo(w * .66, 16)
      ..lineTo(w * .66, 58)
      ..lineTo(w - 32, 58);
    canvas.drawPath(plan, p);
    p
      ..color = OfficeColors.blue
      ..strokeWidth = 2;
    canvas.drawLine(Offset(w * .5, 94), Offset(w * .5, 94 - w * .15), p);
    canvas.drawArc(
      Rect.fromCircle(center: Offset(w * .5, 94), radius: w * .15),
      -math.pi / 2,
      math.pi / 2,
      false,
      p..strokeWidth = 1,
    );
    canvas.drawCircle(
      Offset(w - 32, 16),
      3.5,
      Paint()..color = OfficeColors.blue,
    );
    canvas.restore();
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class WorkspaceView extends StatefulWidget {
  final Map<String, dynamic> user;
  final List<dynamic> projects;
  final Map<String, dynamic>? storage;
  final bool busy;
  final String? error;
  final VoidCallback onRefresh,
      onLogout,
      onNewProject,
      onConnectDrive,
      onUsers,
      onCustomers;
  final void Function(Map<String, dynamic>) onProject;
  final VoidCallback? onInquiries;
  final ValueChanged<String> onSelectStorage;
  const WorkspaceView({
    super.key,
    required this.user,
    required this.projects,
    this.storage,
    required this.busy,
    this.error,
    required this.onRefresh,
    required this.onLogout,
    required this.onNewProject,
    required this.onConnectDrive,
    required this.onSelectStorage,
    required this.onUsers,
    required this.onCustomers,
    required this.onProject,
    this.onInquiries,
  });
  @override
  State<WorkspaceView> createState() => _WorkspaceViewState();
}

class _WorkspaceViewState extends State<WorkspaceView> {
  final search = TextEditingController();
  final searchFocus = FocusNode();
  bool storagePage = false, listView = false, alphabetical = false;
  bool get owner => widget.user['role'] == 'owner';
  @override
  void dispose() {
    search.dispose();
    searchFocus.dispose();
    super.dispose();
  }

  Widget navigation({bool drawer = false}) => Container(
    width: 232,
    decoration: const BoxDecoration(
      color: OfficeColors.sidebar,
      border: Border(right: BorderSide(color: OfficeColors.line)),
    ),
    child: SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(18, 30, 18, 20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Padding(
              padding: EdgeInsets.only(left: 8),
              child: Row(
                children: [
                  PlanMark(size: 33),
                  SizedBox(width: 10),
                  Flexible(
                    child: FittedBox(
                      fit: BoxFit.scaleDown,
                      alignment: Alignment.centerLeft,
                      child: Text(
                        'smartplan',
                        style: TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.w600,
                          letterSpacing: -.8,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 44),
            const Padding(
              padding: EdgeInsets.only(left: 12, bottom: 12),
              child: Eyebrow('Arbeitsbereich'),
            ),
            _NavItem(
              icon: Icons.grid_view_rounded,
              label: 'Projekte',
              selected: !storagePage,
              onTap: () {
                setState(() => storagePage = false);
                if (drawer) Navigator.pop(context);
              },
            ),
            if (owner) ...[
              if (widget.onInquiries != null) ...[
                const SizedBox(height: 5),
                _NavItem(
                  icon: Icons.inbox_outlined,
                  label: 'Anfragen',
                  onTap: () {
                    if (drawer) Navigator.pop(context);
                    widget.onInquiries!();
                  },
                ),
              ],
              const SizedBox(height: 5),
              _NavItem(
                icon: Icons.contacts_outlined,
                label: 'Kunden',
                onTap: () {
                  if (drawer) Navigator.pop(context);
                  widget.onCustomers();
                },
              ),
              const SizedBox(height: 5),
              _NavItem(
                icon: Icons.people_outline_rounded,
                label: 'Benutzerverwaltung',
                onTap: () {
                  if (drawer) Navigator.pop(context);
                  widget.onUsers();
                },
              ),
              const SizedBox(height: 5),
              _NavItem(
                icon: Icons.cloud_outlined,
                label: 'Ablage',
                selected: storagePage,
                onTap: () {
                  setState(() => storagePage = true);
                  if (drawer) Navigator.pop(context);
                },
              ),
            ],
            const Spacer(),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Gute Arbeit beginnt\nmit Überblick.',
                    style: TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w500,
                      letterSpacing: -.5,
                      height: 1.4,
                    ),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Smartplan Office',
                    style: TextStyle(fontSize: 11, color: OfficeColors.muted),
                  ),
                ],
              ),
            ),
            const Divider(),
            const SizedBox(height: 16),
            Row(
              children: [
                Container(
                  width: 34,
                  height: 34,
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: .8),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  alignment: Alignment.center,
                  child: Text(
                    widget.user['email']
                        .toString()
                        .substring(0, 1)
                        .toUpperCase(),
                    style: const TextStyle(
                      fontWeight: FontWeight.w600,
                      color: OfficeColors.muted,
                    ),
                  ),
                ),
                const SizedBox(width: 9),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        roleLabels[widget.user['role']] ?? widget.user['role'],
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      Text(
                        widget.user['email'],
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontSize: 10,
                          color: OfficeColors.muted,
                        ),
                      ),
                      const Text(
                        'Version $smartplanVersion',
                        style: TextStyle(
                          fontSize: 10,
                          color: OfficeColors.muted,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    ),
  );

  @override
  Widget build(BuildContext context) => CallbackShortcuts(
    bindings: {
      SingleActivator(LogicalKeyboardKey.keyF, control: true): () {
        setState(() => storagePage = false);
        searchFocus.requestFocus();
      },
    },
    child: Focus(
      autofocus: true,
      child: LayoutBuilder(
        builder: (context, box) {
          final desktop = box.maxWidth >= 1000;
          final content = Column(
            children: [
              Container(
                height: 78,
                padding: EdgeInsets.symmetric(horizontal: desktop ? 40 : 16),
                decoration: const BoxDecoration(
                  border: Border(bottom: BorderSide(color: OfficeColors.line)),
                ),
                child: Row(
                  children: [
                    if (!desktop)
                      Builder(
                        builder: (context) => IconButton(
                          tooltip: 'Navigation öffnen',
                          onPressed: () => Scaffold.of(context).openDrawer(),
                          icon: const Icon(Icons.menu_rounded),
                        ),
                      ),
                    if (desktop) ...[
                      const Text(
                        'Arbeitsbereich',
                        style: TextStyle(
                          fontSize: 12,
                          color: OfficeColors.muted,
                        ),
                      ),
                      const Padding(
                        padding: EdgeInsets.symmetric(horizontal: 12),
                        child: Icon(
                          Icons.chevron_right_rounded,
                          size: 14,
                          color: OfficeColors.muted,
                        ),
                      ),
                    ],
                    Text(
                      storagePage ? 'Ablage' : 'Projekte',
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                    const Spacer(),
                    if (desktop) ...[
                      Text(
                        _today(),
                        style: const TextStyle(
                          fontSize: 11,
                          color: OfficeColors.muted,
                        ),
                      ),
                      const SizedBox(width: 20),
                    ],
                    IconButton(
                      tooltip: 'Aktualisieren',
                      onPressed: widget.busy ? null : widget.onRefresh,
                      icon: const Icon(Icons.refresh_rounded, size: 20),
                    ),
                    IconButton(
                      tooltip: 'Abmelden',
                      onPressed: widget.busy ? null : widget.onLogout,
                      icon: const Icon(Icons.logout_rounded, size: 19),
                    ),
                  ],
                ),
              ),
              Expanded(
                child: ListView(
                  padding: EdgeInsets.all(desktop ? 40 : 20),
                  children: [
                    if (widget.busy)
                      const Padding(
                        padding: EdgeInsets.only(bottom: 20),
                        child: LinearProgressIndicator(minHeight: 2),
                      ),
                    if (widget.error != null) Notice(widget.error!),
                    if (storagePage) storageContent() else projectsContent(),
                    const SizedBox(height: 30),
                  ],
                ),
              ),
            ],
          );
          return Scaffold(
            drawer: desktop
                ? null
                : Drawer(
                    width: 260,
                    shape: const RoundedRectangleBorder(),
                    child: navigation(drawer: true),
                  ),
            body: SafeArea(
              child: Row(
                children: [
                  if (desktop) navigation(),
                  Expanded(child: content),
                ],
              ),
            ),
          );
        },
      ),
    ),
  );

  Widget projectsContent() {
    final query = search.text.toLowerCase().trim();
    final items = widget.projects
        .where(
          (p) => '${p['name']} ${p['customer']}'.toLowerCase().contains(query),
        )
        .map((p) => Map<String, dynamic>.from(p))
        .toList();
    if (alphabetical)
      items.sort(
        (a, b) => (a['name'] as String).toLowerCase().compareTo(
          (b['name'] as String).toLowerCase(),
        ),
      );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        PageHeading(
          eyebrow: 'Smartplan Office',
          title: 'Alles im Plan.',
          subtitle: 'Ihre Projekte, Dokumente und Freigaben an einem Ort.',
          action: owner
              ? FilledButton.icon(
                  onPressed: widget.busy ? null : widget.onNewProject,
                  icon: const Icon(Icons.add_rounded, size: 18),
                  label: const Text('Projekt anlegen'),
                )
              : null,
        ),
        const SizedBox(height: 32),
        OfficeSurface(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
          child: LayoutBuilder(
            builder: (context, box) => Wrap(
              spacing: 36,
              runSpacing: 20,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      '${widget.projects.length}'.padLeft(2, '0'),
                      style: const TextStyle(
                        fontSize: 34,
                        fontWeight: FontWeight.w500,
                        letterSpacing: -1.5,
                      ),
                    ),
                    const SizedBox(width: 14),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Projekte',
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        Text(
                          owner
                              ? 'In Ihrem Arbeitsbereich'
                              : 'Für Sie freigegeben',
                          style: const TextStyle(
                            fontSize: 11,
                            color: OfficeColors.muted,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
                if (box.maxWidth > 500)
                  Container(width: 1, height: 34, color: OfficeColors.line),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Eyebrow('Ihr Zugang'),
                    const SizedBox(height: 5),
                    Text(
                      roleLabels[widget.user['role']] ?? widget.user['role'],
                      style: const TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 34),
        LayoutBuilder(
          builder: (context, box) {
            final tools = Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                IconButton(
                  tooltip: alphabetical
                      ? 'Ursprüngliche Reihenfolge'
                      : 'Nach Name sortieren',
                  onPressed: () => setState(() => alphabetical = !alphabetical),
                  icon: Icon(
                    Icons.sort_by_alpha_rounded,
                    size: 18,
                    color: alphabetical
                        ? OfficeColors.blue
                        : OfficeColors.muted,
                  ),
                ),
                const SizedBox(width: 6),
                DecoratedBox(
                  decoration: BoxDecoration(
                    color: const Color(0xffe9e9ee),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      IconButton(
                        tooltip: 'Kachelansicht',
                        isSelected: !listView,
                        onPressed: () => setState(() => listView = false),
                        icon: const Icon(Icons.grid_view_rounded, size: 17),
                        style: IconButton.styleFrom(
                          backgroundColor: !listView
                              ? Colors.white
                              : Colors.transparent,
                          foregroundColor: !listView
                              ? OfficeColors.ink
                              : OfficeColors.muted,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
                        ),
                      ),
                      IconButton(
                        tooltip: 'Listenansicht',
                        isSelected: listView,
                        onPressed: () => setState(() => listView = true),
                        icon: const Icon(Icons.view_list_rounded, size: 19),
                        style: IconButton.styleFrom(
                          backgroundColor: listView
                              ? Colors.white
                              : Colors.transparent,
                          foregroundColor: listView
                              ? OfficeColors.ink
                              : OfficeColors.muted,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            );
            final searchBox = TextField(
              controller: search,
              focusNode: searchFocus,
              onChanged: (_) => setState(() {}),
              decoration: InputDecoration(
                hintText: 'Projekte suchen',
                prefixIcon: const Icon(Icons.search_rounded, size: 20),
                suffixIcon: query.isEmpty
                    ? null
                    : IconButton(
                        tooltip: 'Suche zurücksetzen',
                        onPressed: () => setState(search.clear),
                        icon: const Icon(Icons.close_rounded, size: 17),
                      ),
              ),
            );
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(
                      'Projekte',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(width: 10),
                    StatusPill('${items.length}'),
                    const Spacer(),
                    tools,
                  ],
                ),
                const SizedBox(height: 16),
                SizedBox(
                  width: box.maxWidth > 620 ? 340 : double.infinity,
                  child: searchBox,
                ),
              ],
            );
          },
        ),
        const SizedBox(height: 22),
        if (items.isEmpty)
          OfficeSurface(
            child: EmptyState(
              title: query.isEmpty
                  ? 'Noch keine freigegebenen Projekte.'
                  : 'Kein passendes Projekt.',
              description: query.isEmpty
                  ? owner
                        ? 'Legen Sie Ihr erstes Projekt an.\nBerichte und Dokumente finden hier ihren Platz.'
                        : 'Zugewiesene Projekte erscheinen hier.'
                  : 'Versuchen Sie einen anderen Namen oder Kunden.',
            ),
          ),
        if (listView)
          for (final item in items)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: _ProjectCard(
                project: item,
                compact: true,
                enabled: !widget.busy,
                onTap: () => widget.onProject(item),
              ),
            ),
        if (!listView && items.isNotEmpty)
          LayoutBuilder(
            builder: (context, box) {
              final columns = box.maxWidth >= 1100
                  ? 3
                  : box.maxWidth >= 600
                  ? 2
                  : 1;
              final width = (box.maxWidth - (columns - 1) * 18) / columns;
              return Wrap(
                spacing: 18,
                runSpacing: 18,
                children: [
                  for (final item in items)
                    SizedBox(
                      width: width,
                      child: _ProjectCard(
                        project: item,
                        enabled: !widget.busy,
                        onTap: () => widget.onProject(item),
                      ),
                    ),
                ],
              );
            },
          ),
      ],
    );
  }

  List<Map<String, dynamic>>? get storageProviders {
    final source = widget.storage?['providers'];
    if (source is! List) return null;
    final providers = <Map<String, dynamic>>[];
    final seen = <String>{};
    for (final value in source) {
      if (value is! Map ||
          value['id'] is! String ||
          value['label'] is! String ||
          (value['id'] as String).isEmpty ||
          !seen.add(value['id'])) {
        continue;
      }
      providers.add(Map<String, dynamic>.from(value));
    }
    if (!seen.contains('none')) {
      providers.insert(0, {'id': 'none', 'label': 'Noch keine Ablage'});
    }
    return providers;
  }

  Widget storageSelection(List<Map<String, dynamic>> providers) {
    final selected = widget.storage?['selected_provider'];
    final current = providers.where((item) => item['id'] == selected);
    final known = current.isNotEmpty;
    final provider = known ? current.first : null;
    final noStorage = selected == 'none';
    final configured = known && widget.storage?['configured'] == true;
    final requiresConnection = provider?['requires_connection'] == true;
    final connected = known && widget.storage?['connected'] == true;
    final status = !known
        ? 'Ablage nicht verfügbar'
        : noStorage
        ? 'Noch keine Ablage gewählt'
        : !configured
        ? 'Noch nicht eingerichtet'
        : requiresConnection
        ? connected
              ? 'Anmeldung gespeichert'
              : 'Noch nicht verbunden'
        : 'Eingerichtet';
    final description = switch (selected) {
      'server' =>
        'Speichern Sie Dokumente auf dem Server, auf dem Smartplan läuft.',
      'onedrive' => 'Speichern Sie Dokumente im App-Ordner Ihres persönlichen OneDrive-Kontos.',
      'webdav' =>
        'Verbinden Sie einen Cloudspeicher oder ein NAS mit WebDAV-Zugang.',
      'none' => 'Wählen Sie, wo zusätzliche Dokumentkopien abgelegt werden.',
      _ => 'Wählen Sie eine verfügbare Dokumentablage.',
    };
    final setup = switch (selected) {
      'server' => 'Die Serverablage muss zuerst eingerichtet werden.',
      'onedrive' =>
        'Für OneDrive ist zunächst die Microsoft-Einrichtung erforderlich.',
      _ => 'Die Verbindungsdaten für dieses Ziel werden einmal am Smartplan-Server eingerichtet.',
    };
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const IconTile(Icons.folder_copy_outlined),
        const SizedBox(height: 22),
        Text(
          'Ihre Dokumentablage',
          style: Theme.of(context).textTheme.headlineMedium,
        ),
        const SizedBox(height: 20),
        InputDecorator(
          decoration: const InputDecoration(labelText: 'Ablage wählen'),
          child: DropdownButtonHideUnderline(
            child: DropdownButton<String>(
              key: const ValueKey('storage-provider'),
              value: known ? selected as String : null,
              hint: const Text('Bitte auswählen'),
              isExpanded: true,
              isDense: true,
              onChanged: widget.busy
                  ? null
                  : (value) {
                      if (value != null && value != selected) {
                        widget.onSelectStorage(value);
                      }
                    },
              items: [
                for (final item in providers)
                  DropdownMenuItem<String>(
                    value: item['id'],
                    child: Text(item['label'], overflow: TextOverflow.ellipsis),
                  ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 20),
        StatusPill(status),
        const SizedBox(height: 20),
        Text(description, style: const TextStyle(color: OfficeColors.muted)),
        if (known && !noStorage && !configured)
          Padding(
            padding: const EdgeInsets.only(top: 10),
            child: Text(
              setup,
              style: const TextStyle(color: OfficeColors.muted, fontSize: 13),
            ),
          ),
        if (known && !noStorage && requiresConnection) ...[
          const SizedBox(height: 24),
          OutlinedButton.icon(
            onPressed: widget.busy || !configured
                ? null
                : widget.onConnectDrive,
            icon: const Icon(Icons.link_rounded, size: 18),
            label: Text(
              selected == 'onedrive'
                  ? 'Mit OneDrive verbinden'
                  : 'Anmeldung öffnen',
            ),
          ),
        ],
        const SizedBox(height: 24),
        const Text(
          'Ein Wechsel gilt für neue Uploads. Bereits abgelegte Dateien werden nicht verschoben. Berichte und PDFs bleiben in Smartplan verfügbar.',
          style: TextStyle(
            color: OfficeColors.muted,
            fontSize: 12,
            height: 1.6,
          ),
        ),
      ],
    );
  }

  Widget storageContent() => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      const PageHeading(
        eyebrow: 'Ihr Arbeitsbereich',
        title: 'Alles am richtigen Ort.',
        subtitle: 'Ihre Verbindung zur gemeinsamen Dokumentablage.',
      ),
      const SizedBox(height: 32),
      OfficeSurface(
        child: storageProviders != null
            ? storageSelection(storageProviders!)
            : Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const IconTile(Icons.cloud_outlined),
                  const SizedBox(height: 22),
                  Text(
                    'OneDrive Family',
                    style: Theme.of(context).textTheme.headlineMedium,
                  ),
                  const SizedBox(height: 12),
                  StatusPill(
                    widget.storage?['connected'] == true
                        ? 'Anmeldung gespeichert'
                        : widget.storage?['configured'] == true
                        ? 'Noch nicht verbunden'
                        : 'Noch nicht eingerichtet',
                  ),
                  const SizedBox(height: 20),
                  const Text(
                    'Legen Sie unterschriebene PDFs direkt in Ihrem OneDrive-App-Ordner ab.',
                    style: TextStyle(color: OfficeColors.muted),
                  ),
                  if (widget.storage?['configured'] != true)
                    const Padding(
                      padding: EdgeInsets.only(top: 10),
                      child: Text(
                        'Für die Verbindung ist zunächst die Microsoft-Einrichtung erforderlich.',
                        style: TextStyle(
                          color: OfficeColors.muted,
                          fontSize: 13,
                        ),
                      ),
                    ),
                  const SizedBox(height: 24),
                  OutlinedButton.icon(
                    onPressed:
                        widget.busy || widget.storage?['configured'] != true
                        ? null
                        : widget.onConnectDrive,
                    icon: const Icon(Icons.link_rounded, size: 18),
                    label: const Text('OneDrive Family verbinden'),
                  ),
                ],
              ),
      ),
    ],
  );
}

String _today() {
  final d = DateTime.now();
  const months = [
    'Januar',
    'Februar',
    'März',
    'April',
    'Mai',
    'Juni',
    'Juli',
    'August',
    'September',
    'Oktober',
    'November',
    'Dezember',
  ];
  return '${d.day}. ${months[d.month - 1]} ${d.year}';
}

class _NavItem extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool selected;
  final VoidCallback onTap;
  const _NavItem({
    required this.icon,
    required this.label,
    this.selected = false,
    required this.onTap,
  });
  @override
  Widget build(BuildContext context) => Material(
    color: selected ? Colors.white.withValues(alpha: .9) : Colors.transparent,
    borderRadius: BorderRadius.circular(10),
    child: InkWell(
      borderRadius: BorderRadius.circular(10),
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 13),
        child: Row(
          children: [
            Icon(
              icon,
              size: 18,
              color: selected ? OfficeColors.blue : OfficeColors.muted,
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                label,
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
                  color: selected ? OfficeColors.ink : OfficeColors.muted,
                ),
              ),
            ),
          ],
        ),
      ),
    ),
  );
}

class _ProjectCard extends StatelessWidget {
  final Map<String, dynamic> project;
  final bool compact, enabled;
  final VoidCallback onTap;
  const _ProjectCard({
    required this.project,
    required this.onTap,
    this.compact = false,
    this.enabled = true,
  });
  @override
  Widget build(BuildContext context) => Material(
    color: Colors.white,
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(18),
      side: const BorderSide(color: OfficeColors.line),
    ),
    clipBehavior: Clip.antiAlias,
    child: InkWell(
      onTap: enabled ? onTap : null,
      hoverColor: OfficeColors.blueTint.withValues(alpha: .45),
      child: Padding(
        padding: EdgeInsets.all(compact ? 20 : 24),
        child: compact
            ? Row(
                children: [
                  const IconTile(Icons.folder_outlined),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          project['name'],
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        const SizedBox(height: 4),
                        Text(
                          project['customer'],
                          style: const TextStyle(
                            color: OfficeColors.muted,
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const Icon(
                    Icons.chevron_right_rounded,
                    color: OfficeColors.muted,
                    size: 20,
                  ),
                ],
              )
            : Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Row(
                    children: [
                      IconTile(Icons.folder_outlined),
                      Spacer(),
                      Icon(
                        Icons.north_east_rounded,
                        color: OfficeColors.muted,
                        size: 18,
                      ),
                    ],
                  ),
                  const SizedBox(height: 28),
                  Text(
                    project['name'],
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 19,
                      fontWeight: FontWeight.w600,
                      letterSpacing: -.5,
                      height: 1.35,
                    ),
                  ),
                  const SizedBox(height: 5),
                  Text(
                    project['customer'],
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 12,
                      color: OfficeColors.muted,
                    ),
                  ),
                  const SizedBox(height: 24),
                  const Divider(),
                  const SizedBox(height: 15),
                  const Text(
                    'Projekt öffnen',
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w500,
                      color: OfficeColors.muted,
                    ),
                  ),
                ],
              ),
      ),
    ),
  );
}
