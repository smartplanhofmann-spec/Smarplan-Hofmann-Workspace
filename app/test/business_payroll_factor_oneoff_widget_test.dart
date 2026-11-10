import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll_oneoff_cases.dart';
import 'package:smartplan_office/business_payroll_annual_basis.dart';
import 'package:smartplan_office/business_session.dart';
import 'business_payroll_factor_oneoff_test.dart' as data;
import 'business_payroll_oneoff_cases_test.dart' as existing;

class FactorOneoffApi extends OfficeApi {
  FactorOneoffApi():super(apiVersion:'v1'){token='synthetic-factor-oneoff-widget';}
  bool allowed=true;
  bool lose=true,paused=false;
  final reads=<String>[];
  final posts=<Map<String,dynamic>>[];
  @override
  Future<dynamic> call(String path,[Map<String,dynamic>? body]) async {
    reads.add(path);
    if(path.startsWith('/api/business/capabilities'))return {'compatibility_mode':'business','generation':1,'storage_version':10,'readonly':false,'features':['payroll_oneoff_cases','payroll_annual_basis',if(allowed)'payroll_factor_oneoff'],'capabilities':['business_payroll_oneoff_cases','business_payroll_annual_basis'],'permissions':['personnel.read','personnel.approve'],'organization':{'modules':{'personnel':{'enabled':!paused,'visible':true}}}};
    if(path=='/api/me')return {'id':data.f['case']['created_by']};
    if(path.startsWith('/api/business/payroll/one-off-cases/factor-v15/sources?'))return {...data.copy(data.f['case_sources']),'writes_enabled':!paused};
    if(path.startsWith('/api/business/payroll/annual-facts/factor-v2/sources?'))return data.copy(data.f['annual_sources']);
    if(path=='/api/business/payroll/one-off-cases/factor-v15'){
      posts.add(data.copy(body));if(lose){lose=false;throw const ApiException(0,'Controlled accepted factor response lost');}return data.copy(data.f['case']);
    }
    if(path.endsWith('/history'))return {'items':[data.copy(data.f['case'])]};
    throw StateError('Unexpected factor route: $path');
  }
}

void main(){
  testWidgets('actual factor private page displays original factor at390px and clears when its feature is revoked',(t)async{
    t.view.physicalSize=const Size(390,844);t.view.devicePixelRatio=1;addTearDown(t.view.resetPhysicalSize);addTearDown(t.view.resetDevicePixelRatio);
    final api=FactorOneoffApi(),session=BusinessSession(api:api);
    try{
      await session.load();await t.pumpWidget(MaterialApp(home:BusinessPayrollOneoffCasesPage(session:session,employee:data.copy(data.f['employee']),factorMode:true,initialMonth:'2026-10',onOriginal:(_)async{},onCalculate:(_)async{})));await t.pumpAndSettle();
      await existing.press(t,'Einmalbezugsfall 2026-10 · Fassung 1');
      expect(find.text('Belegter ELStAM-Faktor'),findsOneWidget);expect(find.text('0.753'),findsOneWidget);expect(t.takeException(),isNull);
      expect(api.reads.any((path)=>path.startsWith('/api/business/payroll/one-off-cases/factor-v15/sources?')),true);
      api.allowed=false;await session.load();await t.pumpAndSettle();expect(find.text('0.753'),findsNothing);expect(t.takeException(),isNull);
    }finally{await t.pumpWidget(const SizedBox());session.dispose();}
  });
  testWidgets('factor annual page uses explicit V2 sources and shows only the supported annual forms',(t)async{
    final api=FactorOneoffApi(),session=BusinessSession(api:api);
    try{
      await session.load();await t.pumpWidget(MaterialApp(home:BusinessPayrollAnnualBasisPage(session:session,employee:data.copy(data.f['employee']),factorMode:true,onOriginal:(_)async{})));await t.pumpAndSettle();
      expect(find.text('Belegte externe Lohnperiode'),findsNothing);expect(find.text('Lückenlose Jahresbasis zu einem Stichtag'),findsOneWidget);expect(t.takeException(),isNull);
      expect(api.reads.any((path)=>path.startsWith('/api/business/payroll/annual-facts/factor-v2/sources?')),true);
      api.allowed=false;await session.load();await t.pumpAndSettle();expect(find.text('Lückenlose Jahresbasis zu einem Stichtag'),findsNothing);
    }finally{await t.pumpWidget(const SizedBox());session.dispose();}
  });
  test('native factor lost response keeps its original nonce and needs current feature even when replaying through a pause',()async{
    final api=FactorOneoffApi(),session=BusinessSession(api:api),id=data.employee,key='payroll-factor-oneoff-cases-${data.employee}';
    try{
      await session.load();final body=data.copy(data.f['case_command'])..remove('request_id');
      await expectLater(session.command(key,'/payroll/one-off-cases/factor-v15',body,validateResult:payrollOneOffCaseValidator(body,preview:data.copy(data.f['case_preview']))),throwsA(isA<ApiException>()));
      api.allowed=false;await expectLater(session.repeatPayrollOneoffCaseCommand(id,factorMode:true),throwsA(isA<ApiException>()));expect(api.posts.length,1);
      api.allowed=true;api.paused=true;expect(await session.repeatPayrollOneoffCaseCommand(id,factorMode:true),data.f['case']);expect(api.posts[0],api.posts[1]);
    }finally{session.dispose();}
  });
}
