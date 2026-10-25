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
  final VoidCallback? onInquiries, onIntegrations, onBackToWorkspace;
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
    this.onIntegrations,
    this.onBackToWorkspace,
  });
  @override
  State<WorkspaceView> createState() => _WorkspaceViewState();
}

class _WorkspaceViewState extends State<WorkspaceView> {
  final search = TextEditingController();
  final searchFocus = FocusNode();
  bool storagePage = false,
      listView = true,
      alphabetical = false,
      drawerOpen = false;
  bool get owner => widget.user['role'] == 'owner';
  @override
  void dispose() {
    search.dispose();
    searchFocus.dispose();
    super.dispose();
  }

  void focusSearch() {
    setState(() => storagePage = false);
    searchFocus.requestFocus();
  }

  Widget navigation({bool drawer = false}) => Container(
    width: drawer ? 276 : 244,
    decoration: const BoxDecoration(
      color: OfficeColors.sidebar,
      border: Border(right: BorderSide(color: OfficeColors.line)),
    ),
    child: SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 24, 16, 16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8),
              child: Row(
                children: [
                  const PlanMark(size: 34),
                  const SizedBox(width: 10),
                  const Expanded(
                    child: Text(
                      'smartplan',
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontSize: 21,
                        fontWeight: FontWeight.w700,
                        letterSpacing: -.7,
                      ),
                    ),
                  ),
                  if (drawer)
                    IconButton(
                      tooltip: 'Navigation schließen',
                      onPressed: () => Navigator.pop(context),
                      icon: const Icon(Icons.close_rounded, size: 20),
                    ),
                ],
              ),
            ),
            const SizedBox(height: 30),
            Expanded(
              child: SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Padding(
                      padding: EdgeInsets.fromLTRB(12, 0, 12, 10),
                      child: Eyebrow('Arbeitsbereich'),
                    ),
                    _NavItem(
                      icon: Icons.folder_open_rounded,
                      label: 'Projekte',
                      selected: !storagePage,
                      onTap: () {
                        setState(() => storagePage = false);
                        if (drawer) Navigator.pop(context);
                      },
                    ),
                    if (owner) ...[
                      if (widget.onInquiries != null) ...[
                        const SizedBox(height: 4),
                        _NavItem(
                          icon: Icons.inbox_outlined,
                          label: 'Anfragen',
                          onTap: () {
                            if (drawer) Navigator.pop(context);
                            widget.onInquiries!();
                          },
                        ),
                      ],
                      const SizedBox(height: 28),
                      const Padding(
                        padding: EdgeInsets.fromLTRB(12, 0, 12, 10),
                        child: Eyebrow('Organisation'),
                      ),
                      _NavItem(
                        icon: Icons.contacts_outlined,
                        label: 'Kunden',
                        onTap: () {
                          if (drawer) Navigator.pop(context);
                          widget.onCustomers();
                        },
                      ),
                      const SizedBox(height: 4),
                      _NavItem(
                        icon: Icons.people_outline_rounded,
                        label: 'Benutzerverwaltung',
                        onTap: () {
                          if (drawer) Navigator.pop(context);
                          widget.onUsers();
                        },
                      ),
                      const SizedBox(height: 4),
                      _NavItem(
                        icon: Icons.cloud_outlined,
                        label: 'Ablage',
                        selected: storagePage,
                        onTap: () {
                          setState(() => storagePage = true);
                          if (drawer) Navigator.pop(context);
                        },
                      ),
                      if (widget.onIntegrations != null) ...[
                        const SizedBox(height: 4),
                        _NavItem(
                          icon: Icons.hub_outlined,
                          label: 'Integrationen',
                          onTap: () {
                            if (drawer) Navigator.pop(context);
                            widget.onIntegrations!();
                          },
                        ),
                      ],
                    ],
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            const Divider(),
            const SizedBox(height: 18),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8),
              child: Row(
                children: [
                  Container(
                    width: 38,
                    height: 38,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      widget.user['email'].toString().isEmpty
                          ? 'S'
                          : widget.user['email']
                                .toString()
                                .substring(0, 1)
                                .toUpperCase(),
                      style: const TextStyle(
                        fontWeight: FontWeight.w600,
                        color: OfficeColors.blue,
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          roleLabels[widget.user['role']] ??
                              widget.user['role'],
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        Text(
                          widget.user['email'],
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            fontSize: 11,
                            color: OfficeColors.muted,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const Padding(
              padding: EdgeInsets.only(left: 8, top: 14),
              child: Text(
                'Version $smartplanVersion',
                style: TextStyle(fontSize: 11, color: OfficeColors.muted),
              ),
            ),
          ],
        ),
      ),
    ),
  );

  Widget mobileNavigation(BuildContext scaffoldContext) {
    final destinations = <({String label, IconData icon, VoidCallback action})>[
      (
        label: 'Projekte',
        icon: Icons.folder_open_rounded,
        action: () => setState(() => storagePage = false),
      ),
      if (owner && widget.onInquiries != null)
        (
          label: 'Anfragen',
          icon: Icons.inbox_outlined,
          action: widget.onInquiries!,
        ),
      if (owner)
        (
          label: 'Kunden',
          icon: Icons.contacts_outlined,
          action: widget.onCustomers,
        ),
    ];
    return DecoratedBox(
      decoration: const BoxDecoration(
        border: Border(top: BorderSide(color: OfficeColors.line)),
      ),
      child: NavigationBar(
        height: 72,
        selectedIndex: storagePage ? destinations.length : 0,
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
        onDestinationSelected: (index) {
          if (index == destinations.length) {
            Scaffold.of(scaffoldContext).openDrawer();
          } else {
            destinations[index].action();
          }
        },
        destinations: [
          for (final destination in destinations)
            NavigationDestination(
              icon: Icon(destination.icon),
              label: destination.label,
            ),
          const NavigationDestination(
            icon: Icon(Icons.more_horiz_rounded),
            label: 'Mehr',
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) => CallbackShortcuts(
    bindings: {
      const SingleActivator(LogicalKeyboardKey.keyF, control: true):
          focusSearch,
      const SingleActivator(LogicalKeyboardKey.keyF, meta: true): focusSearch,
    },
    child: Focus(
      autofocus: true,
      child: LayoutBuilder(
        builder: (context, box) {
          final desktop = box.maxWidth >= 1000;
          final content = Column(
            children: [
              if (widget.onBackToWorkspace != null)
                Container(
                  color: Colors.white,
                  alignment: Alignment.centerLeft,
                  padding: EdgeInsets.symmetric(
                    horizontal: desktop ? 24 : 8,
                    vertical: 4,
                  ),
                  child: TextButton.icon(
                    key: const ValueKey('workspace-return-overview'),
                    onPressed: widget.onBackToWorkspace,
                    icon: const Icon(Icons.arrow_back_rounded, size: 20),
                    label: const Text('Zur Übersicht'),
                  ),
                ),
              Container(
                height: 68,
                padding: EdgeInsets.symmetric(horizontal: desktop ? 32 : 12),
                decoration: const BoxDecoration(
                  color: Colors.white,
                  border: Border(bottom: BorderSide(color: OfficeColors.line)),
                ),
                child: Row(
                  children: [
                    if (!desktop)
                      Builder(
                        builder: (context) => IconButton(
                          tooltip: 'Navigation öffnen',
                          onPressed: () => Scaffold.of(context).openDrawer(),
                          icon: const Icon(Icons.menu_rounded, size: 22),
                        ),
                      ),
                    Expanded(
                      child: Text(
                        storagePage
                            ? 'Ablage'
                            : desktop
                            ? 'Projektübersicht'
                            : 'Smartplan',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                    if (desktop) ...[
                      Text(
                        _today(),
                        style: const TextStyle(
                          fontSize: 12,
                          color: OfficeColors.muted,
                        ),
                      ),
                      const SizedBox(width: 20),
                    ],
                    IconButton(
                      tooltip: 'Aktualisieren',
                      onPressed: widget.busy ? null : widget.onRefresh,
                      icon: const Icon(Icons.refresh_rounded, size: 21),
                    ),
                    IconButton(
                      tooltip: 'Abmelden',
                      onPressed: widget.busy ? null : widget.onLogout,
                      icon: const Icon(Icons.logout_rounded, size: 20),
                    ),
                  ],
                ),
              ),
              Expanded(
                child: Align(
                  alignment: Alignment.topCenter,
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 1160),
                    child: ListView(
                      padding: EdgeInsets.fromLTRB(
                        desktop ? 32 : 20,
                        28,
                        desktop ? 32 : 20,
                        36,
                      ),
                      children: [
                        if (widget.busy)
                          const Padding(
                            padding: EdgeInsets.only(bottom: 20),
                            child: LinearProgressIndicator(minHeight: 2),
                          ),
                        if (widget.error != null) Notice(widget.error!),
                        if (storagePage)
                          storageContent()
                        else
                          projectsContent(),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          );
          return Scaffold(
            drawer: desktop
                ? null
                : Drawer(
                    width: 276,
                    shape: const RoundedRectangleBorder(),
                    child: navigation(drawer: true),
                  ),
            onDrawerChanged: (open) => setState(() => drawerOpen = open),
            bottomNavigationBar: desktop || drawerOpen
                ? null
                : Builder(builder: mobileNavigation),
            body: SafeArea(
              bottom: false,
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

  Widget projectViewTools() => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Tooltip(
        message: alphabetical
            ? 'Ursprüngliche Reihenfolge'
            : 'Nach Name sortieren',
        child: TextButton.icon(
          onPressed: () => setState(() => alphabetical = !alphabetical),
          icon: const Icon(Icons.sort_by_alpha_rounded, size: 18),
          label: Text(alphabetical ? 'Name A–Z' : 'Sortieren'),
          style: TextButton.styleFrom(
            foregroundColor: alphabetical
                ? OfficeColors.blue
                : OfficeColors.muted,
          ),
        ),
      ),
      const SizedBox(width: 8),
      DecoratedBox(
        decoration: BoxDecoration(
          color: const Color(0xffe9edf2),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            IconButton(
              tooltip: 'Listenansicht',
              isSelected: listView,
              onPressed: () => setState(() => listView = true),
              icon: const Icon(Icons.view_list_rounded, size: 20),
              style: IconButton.styleFrom(
                backgroundColor: listView ? Colors.white : Colors.transparent,
                foregroundColor: listView
                    ? OfficeColors.blue
                    : OfficeColors.muted,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
            ),
            IconButton(
              tooltip: 'Kachelansicht',
              isSelected: !listView,
              onPressed: () => setState(() => listView = false),
              icon: const Icon(Icons.grid_view_rounded, size: 18),
              style: IconButton.styleFrom(
                backgroundColor: !listView ? Colors.white : Colors.transparent,
                foregroundColor: !listView
                    ? OfficeColors.blue
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

  Widget projectsContent() {
    final query = search.text.toLowerCase().trim();
    final items = widget.projects
        .where(
          (p) => '${p['name']} ${p['customer']}'.toLowerCase().contains(query),
        )
        .map((p) => Map<String, dynamic>.from(p))
        .toList();
    if (alphabetical) {
      items.sort(
        (a, b) => (a['name'] as String).toLowerCase().compareTo(
          (b['name'] as String).toLowerCase(),
        ),
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        PageHeading(
          title: 'Projekte',
          subtitle: owner
              ? 'Pläne, Aufgaben und Unterlagen im Blick.'
              : 'Ihre freigegebenen Projektmappen.',
          action: owner
              ? FilledButton.icon(
                  onPressed: widget.busy ? null : widget.onNewProject,
                  icon: const Icon(Icons.add_rounded, size: 19),
                  label: const Text('Projekt anlegen'),
                )
              : null,
        ),
        const SizedBox(height: 26),
        LayoutBuilder(
          builder: (context, box) {
            final wide = box.maxWidth >= 720;
            final searchBox = TextField(
              controller: search,
              focusNode: searchFocus,
              onChanged: (_) => setState(() {}),
              textInputAction: TextInputAction.search,
              decoration: InputDecoration(
                hintText: 'Projekt oder Kunde suchen',
                fillColor: Colors.white,
                prefixIcon: const Icon(Icons.search_rounded, size: 21),
                suffixIcon: query.isEmpty
                    ? null
                    : IconButton(
                        tooltip: 'Suche zurücksetzen',
                        onPressed: () => setState(search.clear),
                        icon: const Icon(Icons.close_rounded, size: 18),
                      ),
              ),
            );
            final count = Text(
              query.isNotEmpty
                  ? '${items.length} Treffer'
                  : '${items.length} ${items.length == 1 ? 'Projekt' : 'Projekte'}',
              style: const TextStyle(fontSize: 13, color: OfficeColors.muted),
            );
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (wide)
                  Row(
                    children: [
                      Expanded(child: searchBox),
                      const SizedBox(width: 16),
                      projectViewTools(),
                    ],
                  )
                else
                  searchBox,
                const SizedBox(height: 12),
                if (wide)
                  count
                else
                  Wrap(
                    alignment: WrapAlignment.spaceBetween,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    spacing: 16,
                    runSpacing: 4,
                    children: [count, projectViewTools()],
                  ),
              ],
            );
          },
        ),
        const SizedBox(height: 18),
        if (items.isEmpty)
          OfficeSurface(
            child: EmptyState(
              title: query.isEmpty
                  ? 'Noch keine freigegebenen Projekte.'
                  : 'Kein passendes Projekt.',
              description: query.isEmpty
                  ? owner
                        ? 'Legen Sie ein Projekt an, um Unterlagen und Arbeitsschritte zu sammeln.'
                        : 'Zugewiesene Projekte erscheinen hier.'
                  : 'Versuchen Sie einen anderen Namen oder Kunden.',
            ),
          ),
        if (listView)
          for (final item in items)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: _ProjectCard(
                key: ValueKey('project-card-${item['id']}'),
                project: item,
                compact: true,
                enabled: !widget.busy,
                onTap: () => widget.onProject(item),
              ),
            ),
        if (!listView && items.isNotEmpty)
          LayoutBuilder(
            builder: (context, box) {
              final columns = box.maxWidth >= 1050
                  ? 3
                  : box.maxWidth >= 650
                  ? 2
                  : 1;
              final width = (box.maxWidth - (columns - 1) * 16) / columns;
              return Wrap(
                spacing: 16,
                runSpacing: 16,
                children: [
                  for (final item in items)
                    SizedBox(
                      width: width,
                      child: _ProjectCard(
                        key: ValueKey('project-card-${item['id']}'),
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
  Widget build(BuildContext context) => Semantics(
    button: true,
    selected: selected,
    child: Material(
      color: selected ? OfficeColors.blueTint : Colors.transparent,
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
          child: Row(
            children: [
              Icon(
                icon,
                size: 21,
                color: selected ? OfficeColors.blue : OfficeColors.muted,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  label,
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
                    color: selected ? OfficeColors.blue : OfficeColors.ink,
                  ),
                ),
              ),
            ],
          ),
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
    super.key,
    required this.project,
    required this.onTap,
    this.compact = false,
    this.enabled = true,
  });
  @override
  Widget build(BuildContext context) {
    final name = project['name']?.toString() ?? '';
    final customer = project['customer']?.toString() ?? '';
    final title = Text(
      name,
      maxLines: 2,
      overflow: TextOverflow.ellipsis,
      style: TextStyle(
        fontSize: compact ? 16 : 19,
        height: 1.35,
        fontWeight: FontWeight.w600,
        letterSpacing: -.3,
      ),
    );
    final subtitle = Text(
      customer.isEmpty ? 'Kunde nicht hinterlegt' : customer,
      maxLines: 2,
      overflow: TextOverflow.ellipsis,
      style: const TextStyle(
        color: OfficeColors.muted,
        fontSize: 13,
        height: 1.45,
      ),
    );
    return Semantics(
      button: true,
      enabled: enabled,
      child: Material(
        color: Colors.white,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: OfficeColors.line),
        ),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: enabled ? onTap : null,
          hoverColor: OfficeColors.blueTint.withValues(alpha: .6),
          child: LayoutBuilder(
            builder: (context, box) => ConstrainedBox(
              constraints: const BoxConstraints(minHeight: 104),
              child: Padding(
                padding: EdgeInsets.all(compact ? 20 : 24),
                child: compact
                    ? Row(
                        children: [
                          const IconTile(Icons.folder_open_rounded),
                          const SizedBox(width: 16),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                title,
                                const SizedBox(height: 5),
                                subtitle,
                              ],
                            ),
                          ),
                          const SizedBox(width: 12),
                          if (box.maxWidth >= 520) ...[
                            const Text(
                              'Öffnen',
                              style: TextStyle(
                                fontSize: 13,
                                color: OfficeColors.blue,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                            const SizedBox(width: 12),
                          ],
                          Container(
                            width: 30,
                            height: 30,
                            decoration: BoxDecoration(
                              color: OfficeColors.blueTint,
                              borderRadius: BorderRadius.circular(9),
                            ),
                            child: const Icon(
                              Icons.chevron_right_rounded,
                              color: OfficeColors.blue,
                              size: 21,
                            ),
                          ),
                        ],
                      )
                    : Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const IconTile(Icons.folder_open_rounded),
                          const SizedBox(height: 22),
                          title,
                          const SizedBox(height: 6),
                          subtitle,
                          const SizedBox(height: 24),
                          const Divider(),
                          const SizedBox(height: 16),
                          const Row(
                            children: [
                              Expanded(
                                child: Text(
                                  'Projektmappe öffnen',
                                  style: TextStyle(
                                    fontSize: 13,
                                    color: OfficeColors.blue,
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                              ),
                              Icon(
                                Icons.arrow_forward_rounded,
                                color: OfficeColors.blue,
                                size: 18,
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
    );
  }
}
