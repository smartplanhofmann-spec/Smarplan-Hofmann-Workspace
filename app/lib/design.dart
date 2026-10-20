import 'package:flutter/material.dart';

abstract final class OfficeColors {
  static const canvas = Color(0xfff5f5f7);
  static const sidebar = Color(0xffeeeef0);
  static const ink = Color(0xff1d1d1f);
  static const muted = Color(0xff6e6e73);
  static const line = Color(0xffe5e5ea);
  static const blue = Color(0xff0066cc);
  static const blueTint = Color(0xffedf4ff);
  static const green = Color(0xff26734d);
}

ThemeData officeTheme() {
  final base = ThemeData(
    useMaterial3: true,
    fontFamily: 'Inter',
    colorScheme: const ColorScheme.light(
      primary: OfficeColors.blue,
      onPrimary: Colors.white,
      secondary: OfficeColors.blue,
      onSecondary: Colors.white,
      secondaryContainer: OfficeColors.blueTint,
      onSecondaryContainer: OfficeColors.blue,
      primaryContainer: OfficeColors.blueTint,
      onPrimaryContainer: OfficeColors.blue,
      surface: Colors.white,
      onSurface: OfficeColors.ink,
      onSurfaceVariant: OfficeColors.muted,
      outline: Color(0xffc7c7cc),
      outlineVariant: OfficeColors.line,
      error: Color(0xffb42318),
    ),
    scaffoldBackgroundColor: OfficeColors.canvas,
  );
  final shape = RoundedRectangleBorder(borderRadius: BorderRadius.circular(12));
  return base.copyWith(
    textTheme: base.textTheme
        .copyWith(
          headlineLarge: const TextStyle(
            fontSize: 38,
            fontWeight: FontWeight.w600,
            letterSpacing: -1.5,
            height: 1.15,
            color: OfficeColors.ink,
          ),
          headlineMedium: const TextStyle(
            fontSize: 28,
            fontWeight: FontWeight.w600,
            letterSpacing: -.8,
            color: OfficeColors.ink,
          ),
          titleLarge: const TextStyle(
            fontSize: 20,
            fontWeight: FontWeight.w600,
            letterSpacing: -.5,
            color: OfficeColors.ink,
          ),
          titleMedium: const TextStyle(
            fontSize: 15,
            fontWeight: FontWeight.w600,
            letterSpacing: -.2,
            color: OfficeColors.ink,
          ),
          bodyLarge: const TextStyle(
            fontSize: 15,
            height: 1.6,
            color: OfficeColors.ink,
          ),
          bodyMedium: const TextStyle(
            fontSize: 14,
            height: 1.55,
            color: OfficeColors.ink,
          ),
          bodySmall: const TextStyle(
            fontSize: 12,
            height: 1.5,
            color: OfficeColors.muted,
          ),
          labelLarge: const TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w600,
            letterSpacing: -.1,
          ),
        )
        .apply(fontFamily: 'Inter'),
    appBarTheme: const AppBarTheme(
      backgroundColor: OfficeColors.canvas,
      foregroundColor: OfficeColors.ink,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      scrolledUnderElevation: 0,
      toolbarHeight: 76,
      titleTextStyle: TextStyle(
        fontFamily: 'Inter',
        fontSize: 17,
        fontWeight: FontWeight.w600,
        letterSpacing: -.4,
        color: OfficeColors.ink,
      ),
    ),
    dividerTheme: const DividerThemeData(
      color: OfficeColors.line,
      thickness: 1,
      space: 1,
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: const Color(0xfffafafa),
      labelStyle: const TextStyle(fontSize: 14, color: OfficeColors.muted),
      hintStyle: const TextStyle(fontSize: 14, color: OfficeColors.muted),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 17),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: OfficeColors.line),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: OfficeColors.line),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: OfficeColors.blue, width: 1.5),
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size(0, 46),
        shape: shape,
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        elevation: 0,
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: OfficeColors.ink,
        minimumSize: const Size(0, 46),
        shape: shape,
        side: const BorderSide(color: OfficeColors.line),
        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        minimumSize: const Size(0, 44),
        shape: shape,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      ),
    ),
    cardTheme: CardThemeData(
      color: Colors.white,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 10),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: const BorderSide(color: OfficeColors.line),
      ),
    ),
    dialogTheme: DialogThemeData(
      backgroundColor: Colors.white,
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
      titleTextStyle: const TextStyle(
        fontFamily: 'Inter',
        fontSize: 23,
        fontWeight: FontWeight.w600,
        letterSpacing: -.6,
        color: OfficeColors.ink,
      ),
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      shape: shape,
      backgroundColor: OfficeColors.ink,
    ),
    checkboxTheme: CheckboxThemeData(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(5)),
    ),
    progressIndicatorTheme: const ProgressIndicatorThemeData(
      color: OfficeColors.blue,
      linearTrackColor: OfficeColors.blueTint,
    ),
    tooltipTheme: TooltipThemeData(
      decoration: BoxDecoration(
        color: OfficeColors.ink,
        borderRadius: BorderRadius.circular(8),
      ),
    ),
  );
}

class PlanMark extends StatelessWidget {
  final double size;
  const PlanMark({super.key, this.size = 38});
  @override
  Widget build(BuildContext context) => Container(
    width: size,
    height: size,
    decoration: BoxDecoration(
      color: OfficeColors.ink,
      borderRadius: BorderRadius.circular(size * .28),
    ),
    child: CustomPaint(painter: _MarkPainter()),
  );
}

class _MarkPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final p = Paint()
      ..color = Colors.white
      ..strokeWidth = size.width * .065
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round
      ..style = PaintingStyle.stroke;
    final w = size.width;
    canvas.drawPath(
      Path()
        ..moveTo(w * .3, w * .68)
        ..lineTo(w * .3, w * .32)
        ..lineTo(w * .7, w * .32)
        ..lineTo(w * .7, w * .5)
        ..lineTo(w * .46, w * .5)
        ..lineTo(w * .46, w * .68),
      p,
    );
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class OfficeSurface extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  const OfficeSurface({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(28),
  });
  @override
  Widget build(BuildContext context) => Container(
    padding: padding,
    decoration: BoxDecoration(
      color: Colors.white,
      borderRadius: BorderRadius.circular(22),
      border: Border.all(color: OfficeColors.line.withValues(alpha: .8)),
      boxShadow: const [
        BoxShadow(
          color: Color(0x04000000),
          blurRadius: 24,
          offset: Offset(0, 8),
        ),
      ],
    ),
    child: Material(type: MaterialType.transparency, child: child),
  );
}

class Eyebrow extends StatelessWidget {
  final String text;
  const Eyebrow(this.text, {super.key});
  @override
  Widget build(BuildContext context) => Text(
    text.toUpperCase(),
    style: const TextStyle(
      fontSize: 10,
      fontWeight: FontWeight.w600,
      letterSpacing: 1.7,
      color: OfficeColors.muted,
    ),
  );
}

class PageHeading extends StatelessWidget {
  final String title, subtitle;
  final String? eyebrow;
  final Widget? action;
  const PageHeading({
    super.key,
    required this.title,
    required this.subtitle,
    this.eyebrow,
    this.action,
  });
  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, box) {
      final heading = Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (eyebrow != null) ...[
            Eyebrow(eyebrow!),
            const SizedBox(height: 12),
          ],
          Text(title, style: Theme.of(context).textTheme.headlineLarge),
          const SizedBox(height: 10),
          Text(
            subtitle,
            style: const TextStyle(
              fontSize: 14,
              height: 1.6,
              color: OfficeColors.muted,
            ),
          ),
        ],
      );
      if (box.maxWidth < 620)
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            heading,
            if (action != null) ...[const SizedBox(height: 20), action!],
          ],
        );
      return Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Expanded(child: heading),
          if (action != null) ...[const SizedBox(width: 24), action!],
        ],
      );
    },
  );
}

class StatusPill extends StatelessWidget {
  final String label;
  final bool positive;
  const StatusPill(this.label, {super.key, this.positive = false});
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
    decoration: BoxDecoration(
      color: positive ? const Color(0xffedf7f0) : OfficeColors.canvas,
      borderRadius: BorderRadius.circular(7),
    ),
    child: Text(
      label,
      style: TextStyle(
        fontSize: 11,
        fontWeight: FontWeight.w500,
        color: positive ? OfficeColors.green : OfficeColors.muted,
      ),
    ),
  );
}

class Notice extends StatelessWidget {
  final String message;
  final bool error;
  const Notice(this.message, {super.key, this.error = true});
  @override
  Widget build(BuildContext context) => Container(
    margin: const EdgeInsets.only(bottom: 20),
    padding: const EdgeInsets.all(16),
    decoration: BoxDecoration(
      color: error ? const Color(0xfffff1ef) : OfficeColors.blueTint,
      borderRadius: BorderRadius.circular(12),
    ),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(
          error
              ? Icons.info_outline_rounded
              : Icons.check_circle_outline_rounded,
          size: 18,
          color: error
              ? Theme.of(context).colorScheme.error
              : OfficeColors.blue,
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Text(
            message,
            style: TextStyle(
              color: error
                  ? Theme.of(context).colorScheme.error
                  : OfficeColors.blue,
            ),
          ),
        ),
      ],
    ),
  );
}

class EmptyState extends StatelessWidget {
  final String title, description;
  final IconData icon;
  const EmptyState({
    super.key,
    required this.title,
    required this.description,
    this.icon = Icons.folder_open_rounded,
  });
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 44, horizontal: 16),
    child: Column(
      children: [
        Container(
          width: 56,
          height: 56,
          decoration: BoxDecoration(
            color: OfficeColors.canvas,
            borderRadius: BorderRadius.circular(16),
          ),
          child: Icon(icon, color: OfficeColors.muted, size: 27),
        ),
        const SizedBox(height: 18),
        Text(
          title,
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 6),
        Text(
          description,
          textAlign: TextAlign.center,
          style: const TextStyle(
            color: OfficeColors.muted,
            fontSize: 13,
            height: 1.6,
          ),
        ),
      ],
    ),
  );
}

class IconTile extends StatelessWidget {
  final IconData icon;
  final Color color;
  const IconTile(this.icon, {super.key, this.color = OfficeColors.blue});
  @override
  Widget build(BuildContext context) => Container(
    width: 42,
    height: 42,
    decoration: BoxDecoration(
      color: color.withValues(alpha: .08),
      borderRadius: BorderRadius.circular(12),
    ),
    child: Icon(icon, color: color, size: 21),
  );
}
