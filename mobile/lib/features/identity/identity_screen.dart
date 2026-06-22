/// «احفظ تقدّمك» — optional Google Sign-In (Phase 1.2).
///
/// Framed as protecting the parent's effort, not as a marketing funnel.
/// The sign-in is opt-in; anonymous use remains the default.
library;

import 'package:flutter/material.dart';

import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/noor_mascot.dart';
import 'identity_service.dart';

class IdentityScreen extends StatefulWidget {
  const IdentityScreen({super.key});

  @override
  State<IdentityScreen> createState() => _IdentityScreenState();
}

class _IdentityScreenState extends State<IdentityScreen> {
  bool _loading = true;
  bool _linked = false;
  String? _email;
  String? _name;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final me = await IdentityService.instance.getServerIdentity();
    if (mounted) {
      setState(() {
        _linked = me['linked'] == true;
        _email = me['email'];
        _name = me['display_name'];
        _loading = false;
      });
    }
  }

  Future<void> _signIn() async {
    setState(() => _loading = true);
    final ok = await IdentityService.instance.signInAndLink();
    if (ok && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('تم ربط الحساب 🤍')),
      );
    }
    await _load();
  }

  Future<void> _unlink() async {
    setState(() => _loading = true);
    await IdentityService.instance.unlink();
    await _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('احفظ تقدّمك')),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : Column(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    const NoorMascot(size: 120),
                    const SizedBox(height: 24),
                    const Text(
                      'احفظ جهدك وتقدّمك',
                      style: TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 12),
                    const Text(
                      'تسجيل الدخول اختياري ويخلي بيانات أطفالك وإنجازاتك محفوظة لو غيّرت الجهاز أو أعدت تثبيت التطبيق.',
                      textAlign: TextAlign.center,
                      style: TextStyle(fontSize: 15, color: Dt.inkSoft),
                    ),
                    const SizedBox(height: 32),
                    if (_linked) ...[
                      const Icon(Icons.verified_outlined, color: AppTheme.primary, size: 48),
                      const SizedBox(height: 12),
                      Text(_name ?? '', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                      if (_email != null && _email!.isNotEmpty)
                        Text(_email!, style: const TextStyle(fontSize: 14, color: Dt.inkSoft)),
                      const SizedBox(height: 24),
                      _Button(
                        label: 'فك الربط',
                        outlined: true,
                        onTap: _unlink,
                      ),
                    ] else ...[
                      _Button(
                        label: 'سجّل بحساب Google',
                        onTap: _signIn,
                      ),
                    ],
                    const Spacer(),
                    const Text(
                      'البيانات تبقى على نفس الجهاز إلا إذا اخترت تسجيل الدخول.',
                      textAlign: TextAlign.center,
                      style: TextStyle(fontSize: 12, color: Dt.inkSoft),
                    ),
                  ],
                ),
        ),
      ),
    );
  }
}

class _Button extends StatelessWidget {
  final String label;
  final VoidCallback onTap;
  final bool outlined;

  const _Button({required this.label, required this.onTap, this.outlined = false});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      child: Material(
        color: outlined ? Colors.transparent : AppTheme.primary,
        borderRadius: BorderRadius.circular(Dt.rButton),
        child: InkWell(
          borderRadius: BorderRadius.circular(Dt.rButton),
          onTap: onTap,
          child: Container(
            padding: const EdgeInsets.symmetric(vertical: 16),
            decoration: BoxDecoration(
              border: outlined ? Border.all(color: AppTheme.primary) : null,
              borderRadius: BorderRadius.circular(Dt.rButton),
            ),
            child: Text(
              label,
              textAlign: TextAlign.center,
              style: TextStyle(
                color: outlined ? AppTheme.primary : Colors.white,
                fontWeight: FontWeight.w700,
                fontSize: 16,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
