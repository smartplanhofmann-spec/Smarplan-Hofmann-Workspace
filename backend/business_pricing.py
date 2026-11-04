"""Explicit Decimal pricing and offer margins; no writes or inferred costs.

Base cost excludes the separately declared BOM and labour. Overhead becomes
cost; markup and surcharge are independent additions on that cost. Every
displayed unit step rounds commercially to cents before the next step.
"""
from decimal import Decimal,localcontext
import json

from core import Problem,canonical


FIELDS={'base_cost_net','labor_hours','hourly_cost_net','components','overhead_percent','overhead_amount',
        'markup_percent','markup_amount','surcharge_percent','surcharge_amount','tax_rate','quantity','unit','kind',
        'source_article_id','source_article_revision','source_price_selection','project_id'}


def cost_known(article):
    """Legacy zero defaults never establish that a purchase cost was captured."""
    from business_documents import decimal_value
    marker=article.get('cost_known')
    if marker is not None and type(marker) is not bool:raise Problem(400,'Kostenbestätigung erwartet')
    return marker if marker is not None else decimal_value(article.get('cost_price_net','0'))>0


def snapshot_matches(position,snapshot,*,office=None):
    """Check a frozen proof against its position, without reading live sources."""
    from business_documents import _hash,decimal_value
    if (not isinstance(snapshot,dict) or not isinstance(snapshot.get('inputs'),dict)
        or snapshot.get('preview_hash')!=_hash(canonical({k:v for k,v in snapshot.items() if k!='preview_hash'}))):
        raise Problem(400,'Kalkulationsnachweis ist ungültig')
    if office is not None:validate_catalog_sources(office,snapshot)
    inputs=snapshot['inputs']
    required={'quantity','unit','kind','tax_rate'}
    if not required<=inputs.keys() or not {'unit_price_net','unit_cost_net'}<=snapshot.keys():raise Problem(400,'Kalkulationsnachweis ist unvollständig')
    for key,expected in (('quantity',inputs['quantity']),('tax_rate',inputs['tax_rate']),
                         ('unit_price_net',snapshot['unit_price_net']),('cost_price_net',snapshot['unit_cost_net']),
                         ('price_base_quantity','1'),('cost_price_base_quantity','1'),('discount_percent','0')):
        actual=position.get(key,'1' if key.endswith('base_quantity') else '0' if key=='discount_percent' else None)
        if actual is None or actual=='':return False
        if decimal_value(actual)!=decimal_value(expected):return False
    rate=decimal_value(inputs['tax_rate'])
    return (position.get('unit')==inputs['unit'] and position.get('kind','service')==inputs['kind']
        and position.get('tax_category','S' if rate else 'Z')==('S' if rate else 'Z')
        and not position.get('tax_exemption_reason'))


def validate_catalog_sources(office,snapshot):
    """Frozen calculations retain dated original facts, not current heads."""
    from business_catalog_prices import validate_snapshot
    from business_documents import decimal_value,_id
    inputs=snapshot.get('inputs',{})
    expected=[]
    if inputs.get('source_article_id') is not None:
        expected.append(dict(article_id=inputs['source_article_id'],article_revision=inputs.get('source_article_revision'),price_selection=inputs.get('source_price_selection')))
    expected.extend(inputs.get('components',[]))
    sources=snapshot.get('source_articles',[])
    components=snapshot.get('components',[])
    has_dated=any(item.get('price_selection') is not None for item in expected) or any(item.get('catalog_price_snapshot') is not None for item in sources+components)
    if not has_dated:return
    if len(sources)!=len(expected) or len(components)!=len(inputs.get('components',[])):
        raise Problem(409,'Datierte Kalkulationsquellen sind unvollständig')
    for source,choice in list(zip(sources,expected))+list(zip(components,inputs.get('components',[]))):
        proof=source.get('catalog_price_snapshot');selection=choice.get('price_selection')
        if proof is None and selection is None:continue
        if not proof or selection!={key:proof.get(key) for key in ('price_id','price_revision','price_sha256','effective_on')}:
            raise Problem(409,'Kalkulationsauswahl und datierter Preisnachweis widersprechen sich')
        identifier=_id(source.get('id'))
        validate_snapshot(office,proof,identifier,'purchase_net')
        article=office.db.execute('SELECT payload_json,payload_sha256 FROM business_article_versions WHERE article_id=? AND revision=?',(identifier,source.get('revision'))).fetchone()
        price=proof['price']
        if (article is None or choice.get('article_id')!=identifier or choice.get('article_revision')!=source.get('revision')
                or article['payload_sha256']!=source.get('payload_sha256')
                or any(json.loads(article['payload_json']).get(key)!=source.get(key) for key in ('name','unit','kind'))
                or decimal_value(source.get('cost_price_net'))!=Decimal(price['price_net'])
                or decimal_value(source.get('cost_price_base_quantity'))!=Decimal(price['price_base_quantity'])
                or source.get('unit')!=price['unit']):
            raise Problem(409,'Kalkulationsquelle stimmt nicht mit dem datierten Preisnachweis überein')
        if 'quantity' in source:
            from business_documents import money
            if (decimal_value(source['quantity'])!=decimal_value(choice.get('quantity'))
                    or source.get('cost_net')!=money(decimal_value(source['quantity'])*Decimal(price['price_net'])/Decimal(price['price_base_quantity']))):
                raise Problem(409,'Stücklistensumme stimmt nicht mit ihrer datierten Bezugsmenge überein')


def preview(office,actor,data,*,lock=False):
    from business_documents import require,decimal_value,money,_id,_text,_hash,calculate_positions
    if not isinstance(data,dict) or set(data)-FIELDS:raise Problem(400,'Begrenzte Preiskalkulation erwartet')
    project=data.get('project_id')
    if project is not None:_id(project)
    require(office,actor,'finance.read',project)
    if lock:
        from business_catalog_prices import lock_selections
        from business_documents import _catalog_selections
        selections=_catalog_selections(data)
        if selections:
            require(office,actor,'finance.read')
            lock_selections(office,selections)
    inputs={};sources=[]
    for key in ('base_cost_net','labor_hours','hourly_cost_net','overhead_percent','overhead_amount','markup_percent','markup_amount','surcharge_percent','surcharge_amount'):
        value=decimal_value(data.get(key,'0'),maximum=Decimal('10000') if key.endswith('_percent') else Decimal('9999999999999'))
        inputs[key]=format(value,'f')
    inputs['quantity']=format(decimal_value(data.get('quantity','1')),'f')
    if Decimal(inputs['quantity'])<=0:raise Problem(400,'Positive Kalkulationsmenge erwartet')
    inputs['tax_rate']=format(decimal_value(data.get('tax_rate','19'),maximum=Decimal(100)).normalize(),'f')
    inputs['unit']=_text(data.get('unit','C62'),'Einheit',20)
    inputs['kind']=data.get('kind','service')
    if inputs['kind'] not in ('material','labor','service','machine'):raise Problem(400,'Kalkulationsart erwartet')
    if project is not None:inputs['project_id']=project

    def article(identifier,revision,*,needs_cost=True,selection=None):
        # Project finance grants do not expose the shared, global cost catalog.
        require(office,actor,'finance.read')
        _id(identifier)
        if type(revision) is not int or revision<1:raise Problem(400,'Erwartete Artikelrevision erforderlich')
        row=office.db.execute('SELECT id,revision,payload_json FROM business_articles WHERE id=?',(identifier,)).fetchone()
        if not row:raise Problem(404,'Kalkulationsartikel nicht verfügbar')
        value=json.loads(row['payload_json'])
        if row['revision']!=revision or value.get('active') is not True:raise Problem(409,'Kalkulationsartikel wurde geändert oder deaktiviert')
        from business_catalog_prices import article_managed,resolve_selection
        proof=None
        if selection is not None:
            proof=resolve_selection(office,actor,identifier,selection,'purchase_net',lock=lock)
        elif article_managed(office,identifier):
            raise Problem(409,'Datierten Einkaufspreis mit ausdrücklichem Preisstand auswählen')
        elif needs_cost and not cost_known(value):
            raise Problem(409,'Stücklistenkosten fehlen; Einkaufspreis ausdrücklich erfassen')
        cost=decimal_value(proof['price']['price_net'] if proof else value.get('cost_price_net','0'))
        basis=decimal_value(proof['price']['price_base_quantity']) if proof else Decimal(1)
        snapshot={'id':identifier,'revision':revision,'payload_sha256':_hash(row['payload_json']),
            'name':value['name'],'unit':value['unit'],'kind':value['kind'],'cost_price_net':format(cost,'f')}
        if proof:snapshot.update(catalog_price_snapshot=proof,cost_price_base_quantity=format(basis,'f'))
        sources.append(snapshot)
        return cost,basis,snapshot

    if 'source_price_selection' in data and not isinstance(data['source_price_selection'],dict):
        raise Problem(400,'Vollständige ausdrückliche Einkaufspreiswahl erforderlich')
    root=data.get('source_article_id');root_cost=None
    if root is not None:
        cost,basis,source=article(root,data.get('source_article_revision'),needs_cost=False,selection=data.get('source_price_selection'))
        inputs.update(source_article_id=root,source_article_revision=data['source_article_revision'])
        if source.get('catalog_price_snapshot'):
            inputs['source_price_selection']=dict(data['source_price_selection'])
            root_cost=(cost,basis)
    elif 'source_article_revision' in data or 'source_price_selection' in data:
        raise Problem(400,'Artikelquelle zur Revision oder Preiswahl erforderlich')
    components=data.get('components',[])
    if not isinstance(components,list) or len(components)>100:raise Problem(400,'Höchstens100 Stücklistenpositionen erwartet')
    inputs['components']=[];component_cost=Decimal(0);component_items=[]
    with localcontext() as context:
        context.prec=38
        for component in components:
            if not isinstance(component,dict) or not {'article_id','article_revision','quantity'}<=set(component)<={'article_id','article_revision','quantity','price_selection'}:raise Problem(400,'Stücklistenartikel, Revision und Menge erwartet')
            if 'price_selection' in component and not isinstance(component['price_selection'],dict):
                raise Problem(400,'Vollständige ausdrückliche Stücklistenpreiswahl erforderlich')
            quantity=decimal_value(component['quantity'],maximum=Decimal('100000'))
            if quantity<=0:raise Problem(400,'Positive Stücklistenmenge erwartet')
            cost,basis,snapshot=article(component['article_id'],component['article_revision'],selection=component.get('price_selection'))
            line=Decimal(money(quantity*cost/basis));component_cost+=line
            chosen={'article_id':component['article_id'],'article_revision':component['article_revision'],'quantity':format(quantity,'f')}
            if 'price_selection' in component:chosen['price_selection']=dict(component['price_selection'])
            inputs['components'].append(chosen)
            component_items.append({**snapshot,'quantity':format(quantity,'f'),'cost_net':money(line)})
        if root_cost:
            bound_base=Decimal(money(root_cost[0]/root_cost[1]))
            if 'base_cost_net' in data and Decimal(inputs['base_cost_net'])!=bound_base:
                raise Problem(409,'Basiskosten stimmen nicht mit der ausgewählten datierten Preisquelle überein')
            inputs['base_cost_net']=money(bound_base)
        base=Decimal(money(Decimal(inputs['base_cost_net'])))
        labour=Decimal(money(Decimal(inputs['labor_hours'])*Decimal(inputs['hourly_cost_net'])))
        direct=base+labour+component_cost
        overhead=Decimal(money(direct*Decimal(inputs['overhead_percent'])/100+Decimal(inputs['overhead_amount'])))
        cost=direct+overhead
        markup=Decimal(money(cost*Decimal(inputs['markup_percent'])/100+Decimal(inputs['markup_amount'])))
        surcharge=Decimal(money(cost*Decimal(inputs['surcharge_percent'])/100+Decimal(inputs['surcharge_amount'])))
        sales=cost+markup+surcharge
        if max(cost,sales)>Decimal('9999999999.99'):raise Problem(400,'Kalkulierter Einzelbetrag überschreitet das Limit')
        calculated=calculate_positions([{'description':'Preiskalkulation','quantity':inputs['quantity'],'unit':inputs['unit'],
            'unit_price_net':money(sales),'tax_rate':inputs['tax_rate'],'kind':inputs['kind']}])['totals']
        total_cost=Decimal(money(Decimal(inputs['quantity'])*cost));total_sales=Decimal(calculated['net']);profit=total_sales-total_cost
        result={'schema_version':1,'currency':'EUR','inputs':inputs,'source_articles':sources,'components':component_items,
            'unit_price_net':money(sales),'unit_cost_net':money(cost),
            'breakdown':{'base_cost_net':money(base),'labor_cost_net':money(labour),'component_cost_net':money(component_cost),
                'direct_cost_net':money(direct),'overhead_net':money(overhead),'markup_net':money(markup),'surcharge_net':money(surcharge),
                'profit_net':money(sales-cost)},
            'totals':{**calculated,'cost_net':money(total_cost),'profit_net':money(profit),
                'margin_percent':money(profit/total_sales*100) if total_sales else None,
                'markup_percent':money(profit/total_cost*100) if total_cost else None},
            'formula':'base + labour + components; overhead on direct cost; markup and surcharge independently on cost including overhead',
            'requires_confirmation':True}
    result['preview_hash']=_hash(canonical(result))
    return result


def offer(positions):
    from business_documents import calculate_positions,decimal_value,money
    calculated=calculate_positions(positions);known=Decimal(0);unknown=[]
    for position in calculated['positions']:
        if 'cost_price_net' not in position:
            unknown.append({'id':position['id'],'index':position['index'],'description':position['description']});continue
        cost=decimal_value(position['cost_price_net']);base=decimal_value(position.get('cost_price_base_quantity','1'))
        if base<=0:raise Problem(400,'Positive Kostenpreisbasis erwartet')
        known+=Decimal(money(Decimal(position['quantity'])*cost/base))
    revenue=Decimal(calculated['totals']['net']);complete=not unknown;profit=revenue-known if complete else None
    return {'currency':'EUR','totals':calculated['totals'],'cost_summary':{'complete':complete,'known_cost_net':money(known),'unknown_positions':unknown},
        'profit_net':money(profit) if profit is not None else None,
        'margin_percent':money(profit/revenue*100) if profit is not None and revenue else None,
        'markup_percent':money(profit/known*100) if profit is not None and known else None}
