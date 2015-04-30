<!--
// downloaded on http://home.nordnet.fr/~lbaillet

pi   = 3.141592653589793238462643383279;
dpi  = pi * 2.0;
rd = pi / 180.0;

ua    = 149.597870e9;  //mètres: Unité astronomique
rayt  = 6378188;       //mètres: rayon moyen de la Terre
light = 299792458;     //mètres par seconde: célérité de la lumière dans le vide
bsa   = 0.996647187;   //rapport du petit-axe et du grand-axe du géoïde
rd    = pi / 180.0;
dr    = 180.0 / pi;
c1    = 3600.0;
ic1   = 1 / c1;
drc1  = dr * c1;
ic1rd = ic1 * rd;
//const float pl_diameter[10] = {1392000e3,4878e3,12104e3,6794e3,142796e3,120000e3,51200e3,48600e3,2200e3,3476e3};
invSunMeanDay = 1/1.002737902965;

//KERNEL***************************************************************************************
function sParamUser(da, mo, an, he, mi, se, lon, lat, alti)
{
	this.da = da;
	this.mo = mo;
	this.an = an;
	this.he = he;
	this.mi = mi;
	this.se = se;
	this.lon = lon;
	this.lat = lat;
	this.alti = alti;
	this.tu = 0.0;
	this.fuso = 0.0;
	this.hete = 0;
}

//Données locales déduites des conditions d'observation
//Ces paramètres sont entièrement calculés
function sLocalData(ParamUser)
{
//	jj, t, t0;              //jour julien, fraction séculaire de jj y compris les heures, minutes..., et idem sans les compléments

	this.lonast = 0.0;
	this.latast = 0.0;
	this.coslatast = 0.0;
	this.sinlatast = 0.0;
	this.cotanlatast = 0.0;
	this.tanlatast = 0.0;
	this.tslrad = 0.0;
	this.tsl0 = 0.0;
	this.tsl = 0.0;
	this.jj = 0.0;
	this.t = 0.0;
	this.t0 = 0.0;
}

function sSySol()
{
	this.u1 = 0.0;
	this.u2 = 0.0;
	this.u3 = 0.0;
	this.u4 = 0.0;
	this.u5 = 0.0;
	this.u6 = 0.0;
	this.u7 = 0.0;
	this.u8 = 0.0;
	this.u9 = 0.0;

	this.l1 = 0.0;
	this.l2 = 0.0;
	this.l3 = 0.0;
	this.l4 = 0.0;
	this.l5 = 0.0;
	this.l6 = 0.0;
	this.l7 = 0.0;
	this.l8 = 0.0;
	this.l9 = 0.0;
	this.l0 = 0.0;

	this.m1 = 0.0;
	this.m2 = 0.0;
	this.m3 = 0.0;
	this.m4 = 0.0;
	this.m5 = 0.0;
	this.m6 = 0.0;
	this.m7 = 0.0;
	this.m8 = 0.0;
	this.m9 = 0.0;
	this.m0 = 0.0;

	this.f = 0.0;
	this.d = 0.0;
	this.o = 0.0;
	this.ob = 0.0;
	this.oba = 0.0;
	this.phi = 0.0;
	this.phiapp = 0.0;

	this.lon = new Array(10);
	this.lat = new Array(10);
	this.r = new Array(10);
	this.delta = new Array(10);
	this.dp = new Array(10);
	this.ap = new Array(10);
	this.dapp = new Array(10);
	this.magnitude = new Array(10);
	this.phase = new Array(10);
	this.elongation = new Array(10);
	this.fraction_illuminee = new Array(10);
}

function tcreg()
{
	this.x0 = 0.0;
	this.y0 = 0.0;
	this.z0 = 0.0;
	this.up = new Array(9);
	this.vp = new Array(9);
	this.wp = new Array(9);
}


//CALC*******************************************************************************************
// Objectif: Calcul du jour julien
// Remarques: Le jour julien est le numéro d'ordre du jour (commençant à 12H TU)
//            dont l'origine (jour julien N°1) est fixée au 2 janvier -4712 à
//            12H.
//
//            Seules les variables pu.da, pu.mo et pu.an sont utilisées. Le
//            résultat est stocké dans ld.jj
//
function CalcJj(pu, ld)
{
  var y, anx, mois;	//int
  var jd;				// double

  y = pu.an;
  mois = pu.mo;
  if (mois < 3)
  {
	 y--;
	 mois = mois + 12;
  }
  jd = Math.floor(365.25*y) + Math.floor(30.6001*(mois+1)) + pu.da + 1720994.5;
  if ((pu.an>1582) ||
		((pu.an>1582) && (pu.mo>10)) ||
		((pu.an>1582) && (pu.mo>10) && (pu.da>14)))
  {
	 anx = Math.floor(y / 100);
	 ld.jj = jd + 2 - anx + Math.floor(anx/4);
  }
  else
    ld.jj = jd;
}


// Objectif: Calcul de paramètres complémentaires sur le temps (ld.t0 qui est
//           la fraction de siècle du jour julien à partir du 1/1/1900 et ld.t
//           qui est égal à ld.t0 augmenté de l'heure locale toujours en
//           fraction de siècle). Le résultat devient indépendant des fuseaux
//           horaires et heures d'été, ce qui donne un référentiel temporel
//           universel.
// Remarques: ld.jj doit avoir déjà été calculé avec CalcJj
//
//            Les variables ld.jj, pu.he, pu.mi, pu.s, pu.fuso, pu.tu et
//            pu.hete sont utilisées.
//
//            Les résultats sont stockés dans ld.t0 et ld.t
//
function CalcT(pu, ld)	//utilise ld.jj, calculé dans CalcJj
{
  ld.t0 = (ld.jj - 2415020.0) / 36525.0;    //ou 2451545 pour origine 1/1/2000

  //Au temps universel on ne prend en compte que heures, minutes et secondes.
  //Autrement, on prend en compte le fuseau horaire et éventuellement l'heure
  //d'été.
  if (pu.tu == 1)
  {
	 ld.t = ld.t0+(pu.he+pu.mi/60.0+pu.se/3600.0)/876600.0;	  //876600=24*36525
  }
  else
  {
	 if (pu.hete)
		ld.t = ld.t0+(pu.he-1+pu.mi/60.0+pu.se/3600.0-pu.fuso)/876600.0;
	 else
		ld.t = ld.t0+(pu.he+pu.mi/60.0+pu.se/3600.0-pu.fuso)/876600.0;
  }
}

// Objectif: Calcul du temps sidéral local.
// Remarques: ld.t0 doit avoir déjà été calculé avec CalcT
//
//            Les variables ld.t0, pu.he, pu.mi, pu.s, pu.fuso, pu.tu et
//            pu.hete sont utilisées.
//
//            Le résultat est stocké dans ld.tsl (et ld.tslrad  sa valeur en
//            radians)
//
function TempsSideralLocal(pu, ld)
{
  var compl;					//double
  var ic1 = 1 / 3600.0;		//const double
  var pi_s_12 = pi / 12.0;	//const double 

  if (pu.tu == 1)
	 compl = 0.0;
  else
  {
	 compl = pu.fuso;
	 if (pu.hete == 1)
		compl = compl + 1.0;
  }
  ld.tsl0 = 6.64606555556 + (8640184.542+0.0929*ld.t0)*ic1*ld.t0;
  ld.tsl = ld.tsl0 - pu.lon/pi_s_12
			  +(1.002737909265+0.589e-10*ld.t0)*(pu.he - compl + pu.mi/60.0 + pu.se*ic1);
  ld.tsl = modulo(ld.tsl, 24);
  ld.tslrad = ld.tsl * pi_s_12;
}

// Objectif: Calcul de la latitude astronomique (et ses autres valeurs
//           trigonométriques) à partir de la latitude terrestre.
// Remarques: "la" est latitude terrestre, ld contiendra la latitude
//            astronomique ainsi que son sinus, son cosus, sa tangeante et
//            cotangeante. La différence entre latitude et latitude
//            astrobnomique est due à la forme en ellipsoide de la Terre.
//
//            Faire attention que "la" ne soit pas particulier (0 ou +/-pi/2)
//            sous peine de division par 0!
function CalcLatAst(lo, la, ld)
{
	ld.lonast = lo*rd;
	bsa = 0.996647187;	//const double
	ld.latast = Math.atan(bsa*bsa*Math.tan(la*rd));
	ld.coslatast = Math.cos(ld.latast);
	ld.sinlatast = Math.sin(ld.latast);
	ld.tanlatast = ld.sinlatast / ld.coslatast;
	ld.cotanlatast = 1.0 / ld.tanlatast;
}

// Objectif: Calcul des paramètres déduits des conditions d'observation
//          (époque et position).
// Remarques: L'ordre d'appel est invariable.
function Calc4EasyParam(pu, ld)
{
  CalcLatAst(pu.lon, pu.lat, ld);
  CalcJj(pu, ld);
  CalcT(pu, ld);
  TempsSideralLocal(pu, ld);
}


//SYSOL**************************************************************************************
// Objectif: Calcul des longitude moyenne (L) et anomalie moyenne (M) pour
//           l'ensemble des planètes, du Soleil et de la Lune. Calcul de
//           l'argument de la latitude (U) pour toutes les planètes.
//           Calcul des variables f (distance angulaire de la Lune moyenne au
//           noed ascendant), d (élongation moyenne de la Lune) et o (longitude
//           du noeud ascendant (oméga)).
function SySol_MeanElements(ld, syso)
{
  syso.l0 = modulo(rd * (279.6964027 + 36000.7695173 * ld.t), dpi);
  syso.l1 = modulo(rd * (178.178814  + 149474.071386 * ld.t), dpi);
  syso.l2 = modulo(rd * (342.766738  + 58519.212542  * ld.t), dpi);
  syso.l3 = modulo(rd * (293.747201  + 19141.699879  * ld.t), dpi);
  syso.l4 = modulo(rd * (237.352259  + 3034.906621   * ld.t), dpi);
  syso.l5 = modulo(rd * (265.869357  + 1222.116843   * ld.t), dpi);
  syso.l6 = modulo(rd * (243.362437  + 429.898403    * ld.t), dpi);
  syso.l7 = modulo(rd * ( 85.024943  + 219.863377    * ld.t), dpi);
  syso.l8 = modulo(rd * ( 92.312712  + 146.674728    * ld.t), dpi);
  syso.l9 = modulo(rd * (270.435377  + 481267.880863 * ld.t), dpi);
  syso.m0 = modulo(rd * (358.4758635 + 35999.0494965 * ld.t), dpi);
  syso.m1 = modulo(rd * (102.279426  + 149472.515334 * ld.t), dpi);
  syso.m2 = modulo(rd * (212.6018923 + 58517.8063877 * ld.t), dpi);
  syso.m3 = modulo(rd * (319.5292728 + 19139.8588872 * ld.t), dpi);
  syso.m4 = modulo(rd * (225.4445943 + 3034.9066206  * ld.t), dpi);
  syso.m5 = modulo(rd * (175.758477  + 1222.116843   * ld.t), dpi);
  syso.m6 = modulo(rd * ( 74.313637  + 429.898403    * ld.t), dpi);
  syso.m7 = modulo(rd * ( 41.269103  + 219.863377    * ld.t), dpi);
  syso.m8 = modulo(rd * (229.488633  + 145.278567    * ld.t), dpi);
  syso.m9 = modulo(rd * (296.095334  + 477198.867586 * ld.t), dpi);
  syso.u1 = modulo(rd * (131.032888  + 149472.885872 * ld.t), dpi);
  syso.u2 = modulo(rd * (266.987445  + 58518.311835  * ld.t), dpi);
  syso.u3 = modulo(rd * (244.960887  + 19140.928953  * ld.t), dpi);
  syso.u4 = modulo(rd * (138.419219  + 3034.906621   * ld.t), dpi);
  syso.u5 = modulo(rd * (153.521637  + 1222.116843   * ld.t), dpi);
  syso.u6 = modulo(rd * (169.872293  + 429.388747    * ld.t), dpi);
  syso.u7 = modulo(rd * (314.346275  + 218.761885    * ld.t), dpi);
  syso.u8 = modulo(rd * (343.369233  + 145.278567    * ld.t), dpi);
  syso.f  = modulo(rd * (11.254075   + 483202.018685 * ld.t), dpi);
  syso.d  = modulo(rd * (350.738975  + 445267.111345 * ld.t), dpi);
  syso.o  = modulo(rd * (259.181303  - 1934.137823   * ld.t), dpi);
}

// Objectif: Calcul des longitude moyenne (L) pour l'ensemble des planètes, du
//           Soleil et de la Lune.
function SySol_MeanLongitude(ld, syso, num)
{
  switch (num)
  {
    case 0: syso.l0 = modulo(rd * (279.6964027 + 36000.7695173 * ld.t), dpi); break;
    case 1: syso.l1 = modulo(rd * (178.178814  + 149474.071386 * ld.t), dpi); break;
    case 2: syso.l2 = modulo(rd * (342.766738  + 58519.212542  * ld.t), dpi); break;
    case 3: syso.l3 = modulo(rd * (293.747201  + 19141.699879  * ld.t), dpi); break;
    case 4: syso.l4 = modulo(rd * (237.352259  + 3034.906621   * ld.t), dpi); break;
    case 5: syso.l5 = modulo(rd * (265.869357  + 1222.116843   * ld.t), dpi); break;
    case 6: syso.l6 = modulo(rd * (243.362437  + 429.898403    * ld.t), dpi); break;
    case 7: syso.l7 = modulo(rd * ( 85.024943  + 219.863377    * ld.t), dpi); break;
    case 8: syso.l8 = modulo(rd * ( 92.312712  + 146.674728    * ld.t), dpi); break;
    case 9: syso.l9 = modulo(rd * (270.435377  + 481267.880863 * ld.t), dpi); break;
  }
}


// Objectif: Calcul des anomalie moyenne (M) pour l'ensemble des planètes, du
//           Soleil et de la Lune.
function SySol_MeanAnomaly(ld, syso, num)
{
  switch (num)
  {
    case 0: syso.m0 = modulo(rd * (358.4758635 + 35999.0494965 * ld.t), dpi); break;
    case 1: syso.m1 = modulo(rd * (102.279426  + 149472.515334 * ld.t), dpi); break;
    case 2: syso.m2 = modulo(rd * (212.6018923 + 58517.8063877 * ld.t), dpi); break;
    case 3: syso.m3 = modulo(rd * (319.5292728 + 19139.8588872 * ld.t), dpi); break;
    case 4: syso.m4 = modulo(rd * (225.4445943 + 3034.9066206  * ld.t), dpi); break;
    case 5: syso.m5 = modulo(rd * (175.758477  + 1222.116843   * ld.t), dpi); break;
    case 6: syso.m6 = modulo(rd * ( 74.313637  + 429.898403    * ld.t), dpi); break;
    case 7: syso.m7 = modulo(rd * ( 41.269103  + 219.863377    * ld.t), dpi); break;
    case 8: syso.m8 = modulo(rd * (229.488633  + 145.278567    * ld.t), dpi); break;
    case 9: syso.m9 = modulo(rd * (296.095334  + 477198.867586 * ld.t), dpi); break;
  }
}


// Objectif: Calcul des arguments de latitude (U) pour l'ensemble des
//           planètes
function SySol_ArgLatitude(ld, syso, num)
{
  switch (num)
  {
    case 1: syso.u1 = modulo(rd * (131.032888  + 149472.885872 * ld.t), dpi); break;
    case 2: syso.u2 = modulo(rd * (266.987445  + 58518.311835  * ld.t), dpi); break;
    case 3: syso.u3 = modulo(rd * (244.960887  + 19140.928953  * ld.t), dpi); break;
    case 4: syso.u4 = modulo(rd * (138.419219  + 3034.906621   * ld.t), dpi); break;
    case 5: syso.u5 = modulo(rd * (153.521637  + 1222.116843   * ld.t), dpi); break;
    case 6: syso.u6 = modulo(rd * (169.872293  + 429.388747    * ld.t), dpi); break;
    case 7: syso.u7 = modulo(rd * (314.346275  + 218.761885    * ld.t), dpi); break;
    case 8: syso.u8 = modulo(rd * (343.369233  + 145.278567    * ld.t), dpi); break;
  }
}


// Objectif: Calcul des variables f (distance angulaire de la Lune moyenne au
//           noed ascendant), d (élongation moyenne de la Lune) et o (longitude
//           du noeud ascendant (oméga)).
function SySol_MoonElements(ld, syso)
{
  syso.f  = modulo(rd * (11.254075   + 483202.018685 * ld.t), dpi);
  syso.d  = modulo(rd * (350.738975  + 445267.111345 * ld.t), dpi);
  syso.o  = modulo(rd * (259.181303  - 1934.137823   * ld.t), dpi);
}


// Objectif: Calcul de la variable o (longitude du noeud ascendant (oméga)).
// Remarques: néant
function SySol_MoonNode(ld, syso)
{
  syso.o  = modulo(rd * (259.181303 - 1934.137823 * ld.t), dpi);
}


// Objectif: Calcul de la longitude vraie du Soleil
// Remarques: Le calcul de l0, m0, m2, m3, m4, m9 doit avoir été effectué
//            préalablement (et pour l'époque t). Idem pour o.
function SySol_RealLonSun(ld, syso)
{
  syso.phi = syso.l0
              + ((6910-17*ld.t)*sin(syso.m0)
              + 72*sin(2*syso.m0) - 7*cos(syso.m0-syso.m4)
              + 6*sin(syso.l9-syso.l0) + 5*sin(4*syso.m0-8*syso.m3+syso.m4)
              - 5*cos(syso.m0-syso.m2) - 4*sin(syso.m0-syso.m2)
              + 4*cos(4*syso.m0-8*syso.m3+syso.m4)
              + 3*sin(2*syso.m0-2*syso.m2) - 3*sin(syso.m4)
              - 3*sin(2*syso.m0-2*syso.m4)
             )*ic1rd;
  //Calcul de phi apparent en prenant en compte l'aberration et la nutation
  syso.phiapp = syso.phi -0.0056932*rd + ((-17.233+0.017*ld.t)*sin(syso.o) - 1.273*sin(2*syso.l0))*ic1rd;
}


// Objectif: Calcul de l'obliquité moyenne (epsilon) de l'écliptique et en
//           tenant compte de la nutation: ea = e+0.00256.cosinus(oméga)
// Remarques: Le calcul de o (longitude du noeud ascendant (oméga)) doit avoir
//            été effectué préalablement (et pour l'époque t).
function SySol_ObqEcliptic(ld, syso)
{
  syso.ob = (23.4522944 - 0.0130125*ld.t - 0.1638e-5*carre(ld.t) + 0.503e-6*cube(ld.t)) * rd;
  syso.oba = syso.ob + 9.21*ic1rd*cos(syso.o);
}

// Objectif: Calcul de la logitude héliocentrique de Mercure pour une époque t
// Remarques: Le calcul de l1, m1, u1, m2 doit avoir été préalablement effectué
function SySol_Lon1(ld, syso)
{
  syso.lon[1] = modulo(ic1rd*(
    syso.l1*drc1 + 8*ld.t*sin(syso.m1) + 84378*sin(syso.m1)
    + 10733*sin(2*syso.m1) + 1892*sin(3*syso.m1)
    + 381*sin(4*syso.m1) + 83*sin(5*syso.m1) + 19*sin(6*syso.m1)
    - 646*sin(2*syso.u1) - 306*sin(syso.m1-2*syso.u1)
    - 274*sin(syso.m1+2*syso.u1) - 92*sin(2*syso.m1+2*syso.u1)
    - 28*sin(3*syso.m1+2*syso.u1) + 25*sin(2*syso.m1-2*syso.u1)
    - 9*sin(4*syso.m1+2*syso.u1) + 7*cos(2*syso.m1-5*syso.m2)
    ),dpi);
}


// Objectif: Calcul de la logitude héliocentrique de Vénus pour une époque t
// Remarques: Le calcul de l2, m2, u2, m0 doit avoir été préalablement effectué
function SySol_Lon2(ld, syso)
{
  syso.lon[2] = modulo(syso.l2 + ic1rd*(
    - 20*ld.t*sin(syso.m2) + 2814*sin(syso.m2)
    + 12*sin(2*syso.m2) - 181*sin(2*syso.u2)
    - 10*cos(2*syso.m0-2*syso.m2) + 7*cos(3*syso.m0-3*syso.m2)
    ),dpi);
}


// Objectif: Calcul de la logitude héliocentrique de Mars pour une époque t
// Remarques: Le calcul de l3, m0, m2, m3, m4, u3 doit avoir été préalablement
//            effectué
function SySol_Lon3(ld, syso)
{
  syso.lon[3] = modulo(ic1rd*(
    syso.l3*drc1 + 37*ld.t*sin(syso.m3) + 4*ld.t*sin(2*syso.m3)
    + 38451*sin(syso.m3) + 2238*sin(2*syso.m3) + 181*sin(3*syso.m3)
    + 17*sin(4*syso.m3) - 52*sin(2*syso.u3) - 22*cos(syso.m3-2*syso.m4)
    - 19*sin(syso.m3-syso.m4) + 17*cos(syso.m3-syso.m4)
    - 16*cos(2*syso.m3-2*syso.m4) + 13*cos(syso.m0-2*syso.m3)
    - 10*sin(syso.m3-2*syso.u3) - 10*sin(syso.m3+2*syso.u3)
    + 7*cos(syso.m0-syso.m3) - 7*cos(2*syso.m0-3*syso.m3)
    - 5*sin(syso.m2-3*syso.m3) - 5*sin(syso.m0-syso.m3)
    - 5*sin(syso.m0-2*syso.m3) - 4*cos(2*syso.m0-4*syso.m3)
    + 4*cos(syso.m4) + 3*cos(syso.m2-3*syso.m3)
    + 3*sin(2*syso.m3-2*syso.m4)
    ),dpi);
}


// Objectif: Calcul de la logitude héliocentrique de Jupiter pour une époque t
// Remarques: Le calcul de l4, m4, m5, m6 doit avoir été préalablement effectué
function SySol_Lon4(ld, syso)
{
  syso.lon[4] = modulo(ic1rd*(
    syso.l4*drc1 + 2511 + 5023*ld.t + 19934*sin(syso.m4) + 601*sin(2*syso.m4)
    + 1093*cos(2*syso.m4-5*syso.m5) - 479*sin(2*syso.m4-5*syso.m5)
    - 185*sin(2*syso.m4-2*syso.m5) + 137*sin(3*syso.m4-5*syso.m5) - 131*sin(syso.m4-2*syso.m5)
    + 79*cos(syso.m4-syso.m5) - 76*cos(2*syso.m4-2*syso.m5)
    - 74*ld.t*cos(syso.m4)+68*ld.t*sin(syso.m4) + 66*cos(2*syso.m4-3*syso.m5)
    + 63*cos(3*syso.m4-5*syso.m5) + 53*cos(syso.m4-5*syso.m5) + 49*sin(2*syso.m4-3*syso.m5)
    - 43*ld.t*sin(2*syso.m4-5*syso.m5) - 37*cos(syso.m4) + 25*sin(2*syso.l4)
    + 25*sin(3*syso.m4) - 23*sin(syso.m4-5*syso.m5) - 19*ld.t*cos(2*syso.m4-5*syso.m5)
    + 17*cos(2*syso.m4-4*syso.m5) + 17*cos(3*syso.m4-3*syso.m5) - 14*sin(syso.m4-syso.m5)
    - 13*sin(3*syso.m4-4*syso.m5) - 9*cos(2*syso.l4) + 9*cos(syso.m5) - 9*sin(syso.m5)
    - 9*sin(3*syso.m4-2*syso.m5) + 9*sin(4*syso.m4-5*syso.m5)
    + 9*sin(2*syso.m4-6*syso.m5 + 3*syso.m6) - 8*cos(4*syso.m4 - 10*syso.m5)
    + 7*cos(3*syso.m4-4*syso.m5) - 7*cos(syso.m4-3*syso.m5) - 7*sin(4*syso.m4-10*syso.m5)
    - 7*sin(syso.m4-3*syso.m5) + 6*cos(4*syso.m4-5*syso.m5) - 6*sin(3*syso.m4-3*syso.m5)
    + 5*cos(2*syso.m5) - 4*sin(4*syso.m4-4*syso.m5) - 4*cos(3*syso.m5) + 4*cos(2*syso.m4-syso.m5)
    - 4*cos(3*syso.m4-2*syso.m5) - 4*ld.t*cos(2*syso.m4) + 3*ld.t*sin(2*syso.m4) + 3*cos(5*syso.m5)
    + 3*cos(5*syso.m4-10*syso.m5) + 3*sin(2*syso.m5) - 2*sin(2*syso.l4-syso.m4) + 2*sin(2*syso.l4+syso.m4)
    - 2*ld.t*sin(3*syso.m4-5*syso.m5) - 2*ld.t*sin(syso.m4-5*syso.m5)
    ),dpi);
}


// Objectif: Calcul de la logitude héliocentrique de Saturne pour une époque t
// Remarques: Le calcul de m4, m5, m6, l5 doit avoir été préalablement effectué
function SySol_Lon5(ld, syso)
{
  syso.lon[5] = modulo(ic1rd*(
    syso.l5*drc1+2507+5014*ld.t+23043*sin(syso.m5)-2689*cos(2*syso.m4-5*syso.m5)
    +1177*sin(2*syso.m4-5*syso.m5)-826*cos(2*syso.m4-4*syso.m5)+802*sin(2*syso.m5)+425*sin(syso.m4-2*syso.m5)
    -229*ld.t*cos(syso.m5)-142*ld.t*sin(syso.m5)-143*cos(2*syso.m4-6*syso.m5)-114*cos(syso.m5)+101*ld.t*sin(2*syso.m4-5*syso.m5)
    -70*cos(2*syso.l5)+67*sin(2*syso.l5)+66*sin(2*syso.m4-6*syso.m5)+60*ld.t*cos(2*syso.m4-5*syso.m5)+41*sin(syso.m4-3*syso.m5)
    +39*sin(3*syso.m5)+31*sin(syso.m4-syso.m5)+31*sin(2*syso.m4-2*syso.m5)-29*cos(2*syso.m4-3*syso.m5)
    -28*sin(2*syso.m4-6*syso.m5+3*syso.m6)+28*cos(syso.m4-3*syso.m5)+22*ld.t*sin(2*syso.m4-4*syso.m5)
    -22*sin(syso.m5-3*syso.m6)+20*sin(2*syso.m4-3*syso.m5)+20*cos(4*syso.m4-10*syso.m5)+19*cos(2*syso.m5-3*syso.m6)
    +19*sin(4*syso.m4-10*syso.m5)-17*ld.t*cos(2*syso.m5)-16*cos(syso.m5-3*syso.m6)-12*sin(2*syso.m4-4*syso.m5)
    +12*cos(syso.m4)-12*sin(2*syso.m5-2*syso.m6)-11*ld.t*sin(2*syso.m5)-11*cos(2*syso.m4-7*syso.m5)+10*sin(2*syso.m5-3*syso.m6)
    +10*cos(2*syso.m4-2*syso.m5)+9*sin(4*syso.m4-9*syso.m5)-8*sin(syso.m5-2*syso.m6)-8*cos(2*syso.l5+syso.m5)
    +8*cos(2*syso.l5-syso.m5)+8*cos(syso.m5-syso.m6)-8*sin(2*syso.l5-syso.m5)+7*sin(2*syso.l5+syso.m5)
    -7*cos(syso.m4-2*syso.m5)-7*cos(2*syso.m5)-6*ld.t*sin(4*syso.m4-10*syso.m5)+6*ld.t*cos(4*syso.m4-10*syso.m5)
    +6*ld.t*sin(2*syso.m4-6*syso.m5)-5*sin(3*syso.m4-7*syso.m5)-5*cos(3*syso.m4-3*syso.m5)-5*cos(2*syso.m5-2*syso.m6)
    +5*sin(3*syso.m4-4*syso.m5)+5*sin(2*syso.m4-7*syso.m5)+4*sin(3*syso.m4-3*syso.m5)+4*sin(3*syso.m4-5*syso.m5)
    +4*ld.t*cos(syso.m4-3*syso.m5)+3*ld.t*cos(2*syso.m4-4*syso.m5)+3*cos(2*syso.m4-6*syso.m5+3*syso.m6)-3*ld.t*sin(2*syso.l5)
    +3*ld.t*cos(2*syso.m4-6*syso.m5)-3*ld.t*cos(2*syso.l5)+3*cos(3*syso.m4-7*syso.m5)+3*cos(4*syso.m4-9*syso.m5)
    +3*sin(3*syso.m4-6*syso.m5)+3*sin(2*syso.m4-syso.m5)+3*sin(syso.m4-4*syso.m5)+2*cos(3*syso.m5-3*syso.m6)
    +2*ld.t*sin(syso.m4-2*syso.m5)+2*sin(4*syso.m5)-2*cos(3*syso.m4-4*syso.m5)-2*cos(2*syso.m4-syso.m5)
    -2*sin(2*syso.m4-7*syso.m5+3*syso.m6)+2*cos(syso.m4-4*syso.m5)+2*cos(4*syso.m4-11*syso.m5)-2*sin(syso.m5-syso.m6)
    ),dpi);
}


// Objectif: Calcul de la logitude héliocentrique d' Uranus pour une époque t
// Remarques: Le calcul de l6, m4, m5, m6, m7, u6 doit avoir été préalablement
//            effectué
function SySol_Lon6(ld, syso)
{
  syso.lon[6] = modulo(ic1rd*(
    syso.l6*drc1+32*ld.t+19397*sin(syso.m6)+570*sin(2*syso.m6)-536*ld.t*cos(syso.m6)+143*sin(syso.m5-2*syso.m6)
    +110*ld.t*sin(syso.m6)+102*sin(syso.m5-3*syso.m6)+76*cos(syso.m5-3*syso.m6)-49*sin(syso.m4-syso.m6)
    -30*ld.t*cos(2*syso.m6)+29*sin(2*syso.m4-6*syso.m5+3*syso.m6)+29*cos(2*syso.m6-2*syso.m7)-28*cos(syso.m6-syso.m7)
    +23*sin(3*syso.m6)-21*cos(syso.m4-syso.m6)+20*sin(syso.m6-syso.m7)+20*cos(syso.m5-2*syso.m6)
    -19*cos(syso.m5-syso.m6)+17*sin(2*syso.m6-3*syso.m7)+14*sin(3*syso.m6-3*syso.m7)+13*sin(syso.m5-syso.m6)
    -12*ld.t*cos(syso.m6)-12*cos(syso.m6)+10*sin(2*syso.m6-2*syso.m7)-9*sin(2*syso.u6)-9*ld.t*sin(syso.m6)
    +9*cos(2*syso.m6-3*syso.m7)+8*ld.t*cos(syso.m5-2*syso.m6)+7*ld.t*cos(syso.m5-3*syso.m6)-7*ld.t*sin(syso.m5-3*syso.m6)
    +7*ld.t*sin(2*syso.m6)+6*sin(2*syso.m4-6*syso.m5+2*syso.m6)+6*cos(2*syso.m4-6*syso.m5+2*syso.m6)
    +5*sin(syso.m5-4*syso.m6)-4*sin(3*syso.m6-4*syso.m7)+4*cos(3*syso.m6-3*syso.m7)-3*cos(syso.m7)-2*sin(syso.m7)
    ),dpi);
}


// Objectif: Calcul de la logitude héliocentrique de Neptune pour une époque t
// Remarques: Le calcul de l6, l7, m4, m5, m6, m7, u7 doit avoir été
//            préalablement effectué
function SySol_Lon7(ld, syso)
{
  syso.lon[7] = modulo(ic1rd*(
    syso.l7*drc1+3523*sin(syso.m7)-50*sin(2*syso.u7)-43*ld.t*cos(syso.m7)+29*sin(syso.m4-syso.m7)
    +19*sin(2*syso.m7)-18*cos(syso.m4-syso.m7)+13*cos(syso.m5-syso.m7)+13*sin(syso.m5-syso.m7)
    -9*sin(2*syso.m6-3*syso.m7)+9*cos(2*syso.m6-2*syso.m7)-5*cos(2*syso.m6-3*syso.m7)-4*ld.t*sin(syso.m7)
    +4*cos(syso.m6-2*syso.m7)+4*ld.t*sin(syso.m7)
    ),dpi);
}


// Objectif: Calcul de la logitude héliocentrique de Pluton pour une époque t
// Remarques: Le calcul de l8, m8, u8 doit avoir été préalablement effectué
function SySol_Lon8(ld, syso)
{
  syso.lon[8] = modulo(ic1rd*(
    syso.l8*drc1+101577*sin(syso.m8)+15517*sin(2*syso.m8)-3593*sin(2*syso.u8)+3414*sin(3*syso.m8)
    -2201*sin(syso.m8-2*syso.m8)-1871*sin(syso.m8+2*syso.u8)+839*sin(4*syso.m8)-757*sin(2*syso.m8+2*syso.u8)
    -285*sin(3*syso.m8+2*syso.u8)+227*ld.t*sin(syso.m8)+218*sin(2*syso.m8-2*syso.u8)+200*ld.t*sin(syso.m8)
    ),dpi);
}


// Objectif: Calcul de la logitude écliptique de la Lune pour une époque t
// Remarques: Le calcul de m9, m0, f, d, o, l2, m, l0 doit avoir été
//            préalablement effectué
function SySol_Lon9(ld, syso)
{
  syso.lon[9] = modulo(ic1rd*(
    syso.l9*c1*dr+22640*sin(syso.m9)-4586*sin(syso.m9-2*syso.d)+2370*sin(2*syso.d)+769*sin(2*syso.m9)-668*sin(syso.m0)
    -412*sin(2*syso.f)-212*sin(2*syso.m9-2*syso.d)-206*sin(syso.m9-2*syso.d+syso.m0)+192*sin(syso.m9+2*syso.d)
    +165*sin(2*syso.d-syso.m0)+148*sin(syso.m9-syso.m0)-125*sin(syso.d)-110*sin(syso.m9+syso.m0)-55*sin(2*syso.f-2*syso.d)
    -45*sin(syso.m9+2*syso.f)+40*sin(syso.m9-2*syso.f)-38*sin(syso.m9-4*syso.d)+36*sin(3*syso.m9)-31*sin(2*syso.m9-4*syso.d)
    +28*sin(syso.m9-2*syso.d-syso.m0)-24*sin(2*syso.d+syso.m0)+19*sin(syso.m9-syso.d)+18*sin(syso.d+syso.m0)
    +15*sin(syso.m9+2*syso.d-syso.m0)+14*sin(2*syso.m9+2*syso.d)+14*sin(4*syso.d)-13*sin(3*syso.m9-2*syso.d)
    -11*sin(syso.m9+16*syso.l0-18*syso.l2)+10*sin(2*syso.m9-syso.m0)+9*sin(syso.m9-2*syso.f-2*syso.d)
    +9*cos(syso.m9+16*syso.l0-18*syso.l2)-9*sin(2*syso.m9-2*syso.d+syso.m0)-8*sin(syso.m9+syso.d)+8*sin(2*syso.d-2*syso.m0)
    -8*sin(2*syso.m9+syso.m0)-7*sin(2*syso.m0)-7*sin(syso.m9-2*syso.d+2*syso.m0)+7*sin(syso.o)-6*sin(syso.m9-2*syso.f+2*syso.d)
    -6*sin(2*syso.f+2*syso.d)-4*sin(syso.m9-4*syso.d+syso.m0)+4*ld.t*cos(syso.m9+16*syso.l0-18*syso.l2)-4*sin(2*syso.m9+2*syso.f)
    +4*ld.t*sin(syso.m9+16*syso.l0-18*syso.l2)+3*sin(syso.m9-3*syso.d)-3*sin(syso.m9+2*syso.d+syso.m0)-3*sin(2*syso.m9-4*syso.d+syso.m0)
    +3*sin(syso.m9-2*syso.m0)+3*sin(syso.m9-2*syso.d-2*syso.m0)-2*sin(2*syso.m9-2*syso.d-syso.m0)-2*sin(2*syso.f-2*syso.d+syso.m0)
    +2*sin(syso.m9+4*syso.d)+2*sin(4*syso.m9)+2*sin(4*syso.d-syso.m0)+2*sin(2*syso.m9-syso.d)
    ),dpi);
}


// Objectif: Calcul de la logitude héliocentrique d'une planète ou de la
//           longitude écliptique de la Lune
// Remarques: Le calcul des longitude moyenne, anomalie moyenne et autres doit
//            avoir été préalablement effectué
function SySol_Lon(ld, syso, pl)
{
  switch (pl)
  {
    case 1: SySol_Lon1(ld, syso);break;
    case 2: SySol_Lon2(ld, syso);break;
    case 3: SySol_Lon3(ld, syso);break;
    case 4: SySol_Lon4(ld, syso);break;
    case 5: SySol_Lon5(ld, syso);break;
    case 6: SySol_Lon6(ld, syso);break;
    case 7: SySol_Lon7(ld, syso);break;
    case 8: SySol_Lon8(ld, syso);break;
    case 9: SySol_Lon9(ld, syso);break;
  }
}


// Objectif: Calcul de la latitude héliocentrique vraie de Mercure pour une
//           époque t
// Remarques: Le calcul de m1, u1 doit avoir été préalablement effectué
function SySol_Lat1(ld, syso)
{
  syso.lat[1] = ic1rd*(
    24134*sin(syso.u1)-10*sin(3*syso.u1)+5180*sin(syso.m1-syso.u1)+4910*sin(syso.m1+syso.u1)
    +1124*sin(2*syso.m1+syso.u1)+271*sin(3*syso.m1+syso.u1)+132*sin(2*syso.m1-syso.u1)+67*sin(4*syso.m1+syso.u1)
    +18*sin(3*syso.m1-syso.u1)+17*sin(5*syso.m1+syso.u1)-9*sin(syso.m1-3*syso.u1)
    );
}


// Objectif: Calcul de la latitude héliocentrique vraie de Vénus pour une
//           époque t
// Remarques: Le calcul de m2, u2 doit avoir été préalablement effectué
function SySol_Lat2(ld, syso)
{
  syso.lat[2] = ic1rd*(
    12215*sin(syso.u2)+83*sin(syso.m2+syso.u2)+83*sin(syso.m2-syso.u2)
    );
}


// Objectif: Calcul de la latitude héliocentrique vraie de Mars pour une
//           époque t
// Remarques: Le calcul de m3, u3 doit avoir été préalablement effectué
function SySol_Lat3(ld, syso)
{
  syso.lat[3] = ic1rd*(
    6603*sin(syso.u3)+622*sin(syso.m3-syso.u3)+615*sin(syso.m3+syso.u3)+64*sin(2*syso.m3+syso.u3)
    );
}


// Objectif: Calcul de la latitude héliocentrique vraie de Jupiter pour une
//           époque t
// Remarques: Le calcul de m4, m5 doit avoir été préalablement effectué
function SySol_Lat4(ld, syso)
{
  syso.lat[4] = ic1rd*(
    -4692*cos(syso.m4)+259*sin(syso.m4)+227-227*cos(2*syso.m4)+30*ld.t*sin(syso.m4)+21*ld.t*cos(syso.m4)
    +16*sin(3*syso.m4-5*syso.m5)-13*sin(syso.m4-5*syso.m5)-12*cos(3*syso.m4)+12*sin(2*syso.m4)
    +7*cos(3*syso.m4-5*syso.m5)-5*cos(syso.m4-5*syso.m5)
    );
}


// Objectif: Calcul de la latitude héliocentrique vraie de Saturne pour une
//           époque t
// Remarques: Le calcul de m4, m5 doit avoir été préalablement effectué
function SySol_Lat5(ld, syso)
{
  syso.lat[5] = ic1rd*(
    185+8297*sin(syso.m5)-3346*cos(syso.m5)+462*sin(2*syso.m5)-189*cos(2*syso.m5)
    +79*ld.t*cos(syso.m5)-71*cos(2*syso.m4-4*syso.m5)+46*sin(2*syso.m4-6*syso.m5)-45*cos(2*syso.m4-6*syso.m5)
    +29*sin(3*syso.m5)-20*cos(2*syso.m4-3*syso.m5)+18*ld.t*sin(syso.m5)-14*cos(2*syso.m4-5*syso.m5)
    -11*cos(3*syso.m5)-10*ld.t+9*sin(syso.m4-3*syso.m5)+8*sin(syso.m4-syso.m5)-6*sin(2*syso.m4-3*syso.m5)
    +5*sin(2*syso.m4-7*syso.m5)-5*cos(2*syso.m4-7*syso.m5)+4*sin(2*syso.m4-5*syso.m5)-4*ld.t*sin(2*syso.m5)
    -3*cos(syso.m4-syso.m5)+3*cos(syso.m4-3*syso.m5)+3*ld.t*sin(2*syso.m4-4*syso.m5)+3*sin(syso.m4-2*syso.m5)
    +2*sin(4*syso.m5)-2*cos(2*syso.m4-2*syso.m5)
    );
}


// Objectif: Calcul de la latitude héliocentrique vraie d'Uranus pour une
//           époque t
// Remarques: Le calcul de m6, u6 doit avoir été préalablement effectué
function SySol_Lat6(ld, syso)
{
  syso.lat[6] = ic1rd*(
    2775*sin(syso.u6)+131*sin(syso.m6-syso.u6)+130*sin(syso.m6+syso.u6)
    );
}


// Objectif: Calcul de la latitude héliocentrique vraie de Neptune pour une
//           époque t
// Remarques: Le calcul de m7, u7 doit avoir été préalablement effectué
function SySol_Lat7(ld, syso)
{
  syso.lat[7] = ic1rd*(
    6404*sin(syso.u7)+55*sin(syso.m7+syso.u7)+55*sin(syso.m7-syso.u7)-33*ld.t*sin(syso.u7)
    );
}


// Objectif: Calcul de la latitude héliocentrique vraie de Pluton pour une
//           époque t
// Remarques: Le calcul de m8, u8 doit avoir été préalablement effectué
function SySol_Lat8(ld, syso)
{
  syso.lat[8] = ic1rd*(
    57726*sin(syso.u8)+15257*sin(syso.m8-syso.u8)+14102*sin(syso.m8+syso.u8)+3870*sin(2*syso.m8+syso.u8)
    +1138*sin(3*syso.m8+syso.u8)+472*sin(2*syso.m8-syso.u8)+353*sin(4*syso.m8+syso.u8)-144*sin(syso.m8-3*syso.u8)
    -119*sin(3*syso.u8)-111*sin(syso.m8+3*syso.u8)
    );
}


// Objectif: Calcul de la latitude écliptique de la Lune pour une époque t
// Remarques: Le calcul de m0, m9, f, d, o doit avoir été préalablement effectué
function SySol_Lat9(ld, syso)
{
  syso.lat[9] = ic1rd*(
    18461*sin(syso.f)+1010*sin(syso.m9+syso.f)+1000*sin(syso.m9-syso.f)-624*sin(syso.f-2*syso.d)-199*sin(syso.m9-syso.f-2*syso.d)
    -167*sin(syso.m9+syso.f-2*syso.d)+117*sin(syso.f+2*syso.d)+62*sin(2*syso.m9+syso.f)+33*sin(syso.m9-syso.f+2*syso.d)+32*sin(2*syso.m9-syso.f)
    -30*sin(syso.f-2*syso.d+syso.m0)-16*sin(2*syso.m9+syso.f-2*syso.d)+15*sin(syso.m9+syso.f+2*syso.d)+12*sin(syso.f-2*syso.d-syso.m0)
    -9*sin(syso.m9-syso.f-2*syso.d+syso.m0)-8*sin(syso.f+syso.o)+8*sin(syso.f+2*syso.d-syso.m0)
    -7*sin(syso.m9+syso.f-2*syso.d+syso.m0)+7*sin(syso.m9+syso.f-syso.m0)-7*sin(syso.m9+syso.f-4*syso.d)-6*sin(syso.f+syso.m0)-6*sin(3*syso.f)+6*sin(syso.m9-syso.f-syso.m0)
    -5*sin(syso.f+syso.d)-5*sin(syso.m9+syso.f+syso.m0)-5*sin(syso.m9-syso.f+syso.m0)+5*sin(syso.f-syso.m0)+5*sin(syso.f-syso.d)
    +4*sin(3*syso.m9+syso.f)-4*sin(syso.f-4*syso.d)-3*sin(syso.m9-syso.f-4*syso.d)
    +3*sin(syso.m9-3*syso.f)-2*sin(2*syso.m9-syso.f-4*syso.d)-2*sin(3*syso.f-2*syso.d)
    +2*sin(2*syso.m9-syso.f+2*syso.d)+2*sin(syso.m9-syso.f+2*syso.d-syso.m0)+2*sin(2*syso.m9-syso.f-2*syso.d)+2*sin(3*syso.m9-syso.f)
    );
}


// Objectif: Calcul de la latitude héliocentrique d'un des corps du système
//           solaire
// Remarques: Le calcul des longitude moyenne, anomalie moyenne et autres doit
//            avoir été préalablement effectué
function SySol_Lat(ld, syso, pl)
{
  switch (pl)
  {
    case 1: SySol_Lat1(ld, syso);break;
    case 2: SySol_Lat2(ld, syso);break;
    case 3: SySol_Lat3(ld, syso);break;
    case 4: SySol_Lat4(ld, syso);break;
    case 5: SySol_Lat5(ld, syso);break;
    case 6: SySol_Lat6(ld, syso);break;
    case 7: SySol_Lat7(ld, syso);break;
    case 8: SySol_Lat8(ld, syso);break;
    case 9: SySol_Lat9(ld, syso);break;
  }
}


// Objectif: Calcul du rayon vecteur Terre-Soleil pour une époque t
// Remarques: Le calcul de m0 doit avoir été préalablement effectué
function SySol_Ray0(ld, syso)
{
  var e1, e2, e3, e4;	//double
  e1  = 0.01675104 - 4.18e-5*ld.t - 1.26e-7*carre(ld.t);
  e2 = carre(e1);
  e3 = e2 * e1;
  e4 = e2 * e2;

  syso.r[0] = 1.00000023*(
    1 + e2*0.5 + (-e1+3/8*e3)*cos(syso.m0)+
    (-0.5*e2+e4/3)*cos(2*syso.m0)+
    (-3/8*e3)*cos(3*syso.m0)-
    e4/3*cos(4*syso.m0)
    )
    +543e-8*sin(rd*(17.9+0.6165298*(ld.jj-2415020-364.5)))
    +1575e-8*sin(rd*(306+1.2330596*(ld.jj-2415020-364.5)))
    +200e-8*sin(rd*(115.9+0.2474593*(ld.jj-2415020-364.5)))
    +345e-8*sin(rd*(222.1+0.858513*(ld.jj-2415020-364.5)))
    +474e-8*sin(rd*(38.3+0.9231589*(ld.jj-2415020-364.5)))
    +1627e-8*sin(rd*(281.6+0.9025161*(ld.jj-2415020-364.5)))
    +927e-8*sin(rd*(291.4+1.80503*(ld.jj-2415020-364.5)))
    +106e-8*sin(rd*(316+0.8194305*(ld.jj-2415020-364.5)))
    +3076e-8*cos(rd*(114.3+12.1907494*(ld.jj-2415020-364.5)));
  syso.delta[0] = syso.r[0];
}


// Objectif: Calcul du rayon vecteur Soleil-Mercure pour une époque t
// Remarques: Le calcul de m1 doit avoir été préalablement effectué
function SySol_Ray1(ld, syso)
{
  syso.r[1] = 0.39528-0.07834*cos(syso.m1)-0.00795*cos(2*syso.m1)-0.00121*cos(3*syso.m1)-0.00022*cos(4*syso.m1);
}


// Objectif: Calcul du rayon vecteur Soleil-Vénus pour une époque t
// Remarques: Le calcul de m2 doit avoir été préalablement effectué
function SySol_Ray2(ld, syso)
{
  syso.r[2] = 0.72335-0.00493*cos(syso.m2);
}


// Objectif: Calcul du rayon vecteur Soleil-Mars pour une époque t
// Remarques: Le calcul de m3 doit avoir été préalablement effectué
function SySol_Ray3(ld, syso)
{
  syso.r[3] = 1.53031-0.14170*cos(syso.m3)-0.00660*cos(2*syso.m3)-0.00047*cos(3*syso.m3);
}


// Objectif: Calcul du rayon vecteur Soleil-Jupiter pour une époque t
// Remarques: Le calcul de m4, m5 doit avoir été préalablement effectué
function SySol_Ray4(ld, syso)
{
  syso.r[4] = 5.20883-0.25122*cos(syso.m4)-0.00604*cos(2*syso.m4)+0.0026*cos(2*syso.m4-2*syso.m5)-
    0.00170*cos(3*syso.m4-5*syso.m5)-0.0016*sin(2*syso.m4-2*syso.m5)-0.00091*ld.t*sin(syso.m4)-
    0.00066*sin(3*syso.m4-5*syso.m5)+0.00063*sin(syso.m4-syso.m5)-0.00051*cos(2*syso.m4-3*syso.m5)-
    0.00046*sin(syso.m4)-0.000029*cos(syso.m4-5*syso.m5)+0.00027*cos(syso.m4-2*syso.m5)-
    0.00022*cos(3*syso.m4)-0.00021*sin(2*syso.m4-5*syso.m5);
}


// Objectif: Calcul du rayon vecteur Soleil-Saturne pour une époque t
// Remarques: Le calcul de m4, m5, m6 doit avoir été préalablement effectué
function SySol_Ray5(ld, syso)
{
  syso.r[5] = 9.55774-0.00028*ld.t-0.53252*cos(syso.m5)-0.01878*sin(2*syso.m4-4*syso.m5)-
    0.01482*cos(2*syso.m5)+0.00817*sin(syso.m4-syso.m5)-0.00539*cos(syso.m4-2*syso.m5)-
    0.00524*ld.t*sin(syso.m5)+0.00349*sin(2*syso.m4-5*syso.m5)+0.00347*sin(2*syso.m4-6*syso.m5)-
    0.00126*cos(2*syso.m4-2*syso.m5)+0.00104*cos(syso.m4-syso.m5)+0.00101*cos(2*syso.m4-5*syso.m5)+
    0.00098*cos(syso.m4-3*syso.m5)-0.00073*cos(2*syso.m4-3*syso.m5)-0.00062*cos(3*syso.m5)+
    0.00042*sin(2*syso.m5-3*syso.m6)+0.00041*sin(2*syso.m4-2*syso.m5)-0.00040*sin(syso.m4-3*syso.m5)+
    0.0004*cos(2*syso.m4-4*syso.m5)-0.00023*sin(syso.m4)+0.00020*sin(2*syso.m4-7*syso.m5);
}


// Objectif: Calcul du rayon vecteur Soleil-Uranus pour une époque t
// Remarques: Le calcul de m5, m6, m7 doit avoir été préalablement effectué
function SySol_Ray6(ld, syso)
{
  syso.r[6] = 19.21216-0.90154*cos(syso.m6)-0.02488*ld.t*sin(syso.m6)-0.02121*cos(2*syso.m6)-
    0.00585*cos(syso.m5-2*syso.m6)-0.00508*ld.t*cos(syso.m6)-0.00451*cos(syso.m4-syso.m6)+
    0.00336*sin(syso.m5-syso.m6)+0.00198*sin(syso.m4-syso.m6)+0.00118*cos(syso.m5-3*syso.m6)+
    0.00107*sin(syso.m5-2*syso.m6)-0.00103*ld.t*sin(2*syso.m6)-0.00081*cos(3*syso.m6-3*syso.m7);
}


// Objectif: Calcul du rayon vecteur Soleil-Neptune pour une époque t
// Remarques: Le calcul de m4, m5, m6, m7, l6 doit avoir été préalablement
//            effectué
function SySol_Ray7(ld, syso)
{
  syso.r[7] = 30.07175-0.25701*cos(syso.m7)-0.00787*cos(2*syso.l6-syso.m6-2*syso.l7)+
    0.00409*cos(syso.m4-syso.m7)-0.00314*ld.t*sin(syso.m7)+0.0025*sin(syso.m4-syso.m7)-
    0.00194*sin(syso.m5-syso.m7)+0.00185*cos(syso.m5-syso.m7);
}


// Objectif: Calcul du rayon vecteur Soleil-Pluton pour une époque t
// Remarques: Le calcul de m8 doit avoir été préalablement effectué
function SySol_Ray8(ld, syso)
{
  syso.r[8] = 40.74638-9.58235*cos(syso.m8)-1.16703*cos(2*syso.m8)-0.22649*cos(3*syso.m8)
    -0.04996*cos(4*syso.m8);
}


// Objectif: Calcul du rayon vecteur Terre-Lune pour une époque t
// Remarques: Le calcul de m0, m9, f, d, o doit avoir été préalablement effectué
function SySol_Ray9(ld, syso)
{
  syso.r[9] = 60.36298-3.27746*cos(syso.m9)-0.57994*cos(syso.m9-2*syso.d)-0.46357*cos(2*syso.d)-0.08904*cos(2*syso.m9)+
    0.03865*cos(2*syso.m9-2*syso.d)-0.03237*cos(2*syso.d-syso.m0)-0.02688*cos(syso.m9+2*syso.d)-0.02358*cos(syso.m9-2*syso.d+syso.m0)-
    0.0203*cos(syso.m9-syso.m0)+0.01719*cos(syso.d)+0.01671*cos(syso.m9+syso.m0)+0.01247*cos(syso.m9-2*syso.f)+0.00704*cos(syso.m0)+
    0.00529*cos(2*syso.d+syso.m0)-0.00524*cos(syso.m9-4*syso.d)+0.00398*cos(syso.m9-2*syso.d-syso.m0)-0.00366*cos(3*syso.m9)-
    0.00295*cos(2*syso.m9-4*syso.d)-0.00263*cos(syso.d+syso.m0)+0.00249*cos(3*syso.m9-2*syso.d)-0.00221*cos(syso.m9+2*syso.d-syso.m0)+
    0.00185*cos(2*syso.f-2*syso.d)-0.00161*cos(2*syso.d-2*syso.m0)+0.00147*cos(syso.m9+2*syso.f-2*syso.d)-0.00142*cos(4*syso.d)+
    0.00139*cos(2*syso.m9-2*syso.d+syso.m0)-0.00118*cos(syso.m9-4*syso.d+syso.m0)-0.00116*cos(2*syso.m9+2*syso.d)-0.0011*cos(2*syso.m9-syso.m0);
}


// Objectif: Calcul du rayon vecteur pour un des corps du système solaire
// Remarques: Le calcul des longitude moyenne, anomalie moyenne et autres doit
//            avoir été préalablement effectué
function SySol_Ray(ld, syso, pl)
{
  switch (pl)
  {
    case 0: SySol_Ray0(ld, syso);break;
    case 1: SySol_Ray1(ld, syso);break;
    case 2: SySol_Ray2(ld, syso);break;
    case 3: SySol_Ray3(ld, syso);break;
    case 4: SySol_Ray4(ld, syso);break;
    case 5: SySol_Ray5(ld, syso);break;
    case 6: SySol_Ray6(ld, syso);break;
    case 7: SySol_Ray7(ld, syso);break;
    case 8: SySol_Ray8(ld, syso);break;
    case 9: SySol_Ray9(ld, syso);break;
  }
}


// Objectif: Calcul de la longitue moyenne, de l'anomalie moyenne, de
//           l'argument de latitude, de la logitude héliocentrique, de la
//           latitude héliocentrique et du rayon vecteur
// Remarques: Le calcul des éventuelles longitude moyenne, anomalie moyenne et
//            argument de latitude doit avoir été préalablement effectué
function SySol_LMULLR(ld, syso, pl)
{
  SySol_MeanLongitude(ld, syso, pl);
  SySol_MeanAnomaly(ld, syso, pl);
  SySol_ArgLatitude(ld, syso, pl);
  SySol_Lon(ld, syso, pl);
  SySol_Lat(ld, syso, pl);
  SySol_Ray(ld, syso, pl);
}


// Objectif: Calcul de la logitude héliocentrique, de la latitude
//           héliocentrique et du rayon vecteur et calculant au besoin d'autres
//           longitude moyenne, anomalie moyenne et argument de latitude
// Remarques: néant
function SysSol_LonLatRay(ld, syso, pl)
{
  switch (pl)
  {
    case 1:
      SySol_MeanAnomaly(ld, syso, 2);
      SySol_LMULLR(ld, syso, 1);
      break;
    case 2:
      SySol_MeanAnomaly(ld, syso, 0);
      SySol_LMULLR(ld, syso, 2);
      break;
    case 3:
      SySol_MeanAnomaly(ld, syso, 0);
      SySol_MeanAnomaly(ld, syso, 2);
      SySol_MeanAnomaly(ld, syso, 4);
      SySol_LMULLR(ld, syso, 3);
      break;
    case 4:
      SySol_MeanAnomaly(ld, syso, 5);
      SySol_MeanAnomaly(ld, syso, 6);
      SySol_LMULLR(ld, syso, 4);
      break;
   case 5:
      SySol_MeanAnomaly(ld, syso, 4);
      SySol_MeanAnomaly(ld, syso, 6);
      SySol_LMULLR(ld, syso, 5);
      break;
   case 6:
      SySol_MeanAnomaly(ld, syso, 4);
      SySol_MeanAnomaly(ld, syso, 5);
      SySol_MeanAnomaly(ld, syso, 7);
      SySol_LMULLR(ld, syso, 6);
      break;
   case 7:
      SySol_MeanLongitude(ld, syso, 6);
      SySol_MeanAnomaly(ld, syso, 4);
      SySol_MeanAnomaly(ld, syso, 5);
      SySol_MeanAnomaly(ld, syso, 6);
      SySol_LMULLR(ld, syso, 7);
      break;
   case 8:
      SySol_LMULLR(ld, syso, 8);
      break;
   case 9:
      SySol_MoonElements(ld, syso);
      SySol_MeanLongitude(ld, syso, 9);
      SySol_MeanAnomaly(ld, syso, 9);
      SySol_MeanLongitude(ld, syso, 0);
      SySol_MeanAnomaly(ld, syso, 0);
      SySol_MeanLongitude(ld, syso, 2);
      SySol_Lon9(ld, syso);
      SySol_Lat9(ld, syso);
      SySol_Ray9(ld, syso);
      break;
  }
}


// Objectif: Calcul des coordonnées rectangulaires équatoriales géocentriques
//           du Soleil
// Remarques: Le rayon vecteur Soleil-Terre, l'obliquité et la longitude vraie
//            doivent avoir été préalablement calculés
function SySol_CREGsun(syso, creg)
{
  creg.x0 = syso.r[0]*cos(syso.phi);
  creg.y0 = syso.r[0]*sin(syso.phi)*cos(syso.oba);
  creg.z0 = syso.r[0]*sin(syso.phi)*sin(syso.oba);
}


// Objectif: Calcul des coordonnées rectangulaires équatoriales géocentriques
//           d'une planète ainsi que la distance planète-Terre
// Remarques: la longitude du noeud ascendant de la Lune, la longitude moyenne
//            de la Lune, l'obliquité, les longitude et latitude héliocentriques
//            de la planète, ainsi que les coordonnées rectangulaires du Soleil
//            doivent avoir été préalablement calculés
function SySol_CREGplanet(ld, syso, creg, pl)
{
  var lat, coslat, sinlat, lonp, coslon, sinlon, obq, cosob, sinob;	//double

  //Correction de la longitude due à la nutation
  lonp = syso.lon[pl] + (-17.233+0.017*ld.t)*ic1rd*sin(syso.o) - 1.273*ic1rd*sin(2*syso.l0);

  //affectation des variables externes dans des variables locales
  lat = syso.lat[pl];
  obq = syso.oba;

  cosob = cos(syso.ob);
  sinob = sin(syso.ob);
  coslon = cos(lonp);
  sinlon = sin(lonp);
  coslat = cos(lat);
  sinlat = sin(lat);
  creg.up[pl] = syso.r[pl]*coslat*coslon + creg.x0;
  creg.vp[pl] = syso.r[pl]*(coslat*sinlon*cosob - sinlat*sinob) + creg.y0;
  creg.wp[pl] = syso.r[pl]*(coslat*sinlon*sinob + sinlat*cosob) + creg.z0;
  syso.delta[pl] = Math.sqrt(carre(creg.up[pl]) + carre(creg.vp[pl]) + carre(creg.wp[pl]));
}

// Objectif: Calcul des coordonnées équatoriales (astrographique et
//           géocentrique) d'une planète
// Remarques: rien n'est à calculer au préalable
function SySol_ADplanet(ld, syso, pl)
{
  var creg;		//tcreg
  creg = new tcreg();
  var ld_copy;	//LocalData
  ld_copy = new sLocalData();
  var tau;		//double
  var conversion = ua / light / 86400 / 36525;	//double const

  //Calcul des longitude et latitude héliocentriques de la planète
  SysSol_LonLatRay(ld, syso, pl);

  //Calcul d'éléments nécessaires au calcul de la longitude vraie du Soleil
  SySol_MeanLongitude(ld, syso, 0);
  SySol_MeanLongitude(ld, syso, 9);
  SySol_MeanAnomaly(ld, syso, 0);
  SySol_MeanAnomaly(ld, syso, 2);
  SySol_MeanAnomaly(ld, syso, 3);
  SySol_MeanAnomaly(ld, syso, 4);
  SySol_MoonNode(ld, syso);   
  SySol_RealLonSun(ld, syso);        //Longitude vraie du Soleil

  //Calcul des coordonnées rectangulaires de la planète
  SySol_Ray0(ld, syso);
  SySol_ObqEcliptic(ld, syso);
  SySol_CREGsun(syso, creg);
  SySol_CREGplanet(ld, syso, creg, pl);

  //Calcul du temps (en fraction de siècle) que met la lumière pour parcourir
  //la distance planète-Terre:
  tau = syso.delta[pl] * conversion; //temps = distance * inverse de la vitesse
  ld_copy = ld;			//¤¤¤
  ld_copy.t = ld.t - tau;
  ld_copy.t0 = ld.t0 - tau;

  //Deuxième itération (sans recalculer les coordonnées du Soleil)
  SysSol_LonLatRay(ld_copy, syso, pl);
  SySol_MoonNode(ld, syso);    
  SySol_ObqEcliptic(ld_copy, syso);
  SySol_CREGplanet(ld_copy, syso, creg, pl);

  //On en déduit les coordonnées équatoriales géocentriques et astrographiques de la planète
  syso.dp[pl] = Math.asin(creg.wp[pl] / syso.delta[pl]);
  syso.ap[pl] = Math.atan(creg.vp[pl] / creg.up[pl]);
  if (creg.up[pl] < 0)
    syso.ap[pl] = syso.ap[pl] + pi;
  else
  {
    if (syso.ap[pl] < 0) syso.ap[pl] = syso.ap[pl] + dpi;
  }
}


// Objectif: Calcul des coordonnées équatoriales (géocentrique) du Soleil
function SySol_ADsun(ld, syso)
{
  //Calcul d'éléments nécessaires au calcul de la longitude vraie du Soleil
  SySol_MoonNode(ld, syso);
  SySol_MeanLongitude(ld, syso, 0);
  SySol_MeanLongitude(ld, syso, 9);
  SySol_MeanAnomaly(ld, syso, 0);
  SySol_MeanAnomaly(ld, syso, 2);
  SySol_MeanAnomaly(ld, syso, 3);
  SySol_MeanAnomaly(ld, syso, 4);
  SySol_RealLonSun(ld, syso);        //Longitude vraie du Soleil
  SySol_Ray0(ld, syso);

  //Calcul de l'obliquité de l'écliptique
  SySol_ObqEcliptic(ld, syso);

  //On en déduit les coordonnées équatoriales géocentriques du Soleil
  syso.dp[0] = Math.asin(sin(syso.oba) * sin(syso.phiapp));
  syso.ap[0] = Math.atan(cos(syso.oba) * sin(syso.phiapp) / cos(syso.phiapp));
  if (cos(syso.phiapp) < 0)
    syso.ap[0] = syso.ap[0] + pi;
  else
  {
    if (syso.ap[0] < 0) syso.ap[0] = syso.ap[0] + dpi;
  }
}


// Objectif: Calcul des coordonnées équatoriales (géocentrique) de la Lune
function SySol_ADmoon(ld, syso)
{
  var re;	//double

  SySol_MoonElements(ld, syso);
  SysSol_LonLatRay(ld, syso, 9);

  //Correction de la longitude due à la nutation
  SySol_ObqEcliptic(ld, syso);
  SySol_MeanLongitude(ld, syso, 0);
  SySol_MeanAnomaly(ld, syso, 0);
  re = syso.lon[9] + ((-17.233+0.017*ld.t)*sin(syso.o) - 1.273*sin(2*syso.l0))*ic1rd;

  //On en déduit les coordonnées équatoriales géocentriques de la Lune
  syso.dp[9] = Math.asin(cos(syso.lat[9])*sin(re)*sin(syso.oba)+sin(syso.lat[9])*cos(syso.oba));
  syso.ap[9] = cos(syso.lat[9])*sin(re)*cos(syso.oba)-sin(syso.lat[9])*sin(syso.oba);
  syso.ap[9] = Math.atan(syso.ap[9]/(cos(syso.lat[9])*cos(re)));
  if (cos(syso.lat[9])*cos(re) < 0)
    syso.ap[9] = syso.ap[9] + pi;
  else
  {
    if (syso.ap[9] < 0) syso.ap[9] = syso.ap[9] + dpi;
  }
}


// Objectif: Calcul des coordonnées équatoriales (astrographique et
//           géocentrique) des planètes, de la Lune et du Soleil
function SySol_AD10(ld, syso)
{
  var pl;		//int
  var creg;		//tcreg 
  creg = new tcreg();
  var ld_copy;	//LocalData
  ld_copy = new sLocalData();
  var tau;		//double
  var re;		//double
  var conversion = ua / light / 86400 / 36525;	//double

  /////////////////////////////////////////////////////////////////////////////
  //Calcul des coordonnées planétaires

  //Calcul des paramètres primaires
  SySol_MoonNode(ld, syso);
  SySol_MeanElements(ld, syso);
  SySol_RealLonSun(ld, syso);        //Longitude vraie du Soleil
  SySol_ObqEcliptic(ld, syso);
  SySol_Ray0(ld, syso);
  SySol_CREGsun(syso,creg);

  //Première itération pour l'ensemble des planètes
  for (pl=1; pl<9; pl++)
  {
    SySol_Lon(ld, syso, pl);
    SySol_Lat(ld, syso, pl);
    SySol_Ray(ld, syso, pl);
    SySol_CREGplanet(ld, syso, creg, pl);
  }

  //Deuxième itération pour l'ensemble des planètes et calcul final
  for (pl=1; pl<9; pl++)
  {
    //Calcul du temps (en fraction de siècle) que met la lumière pour parcourir
    //la distance planète-Terre:
    tau = syso.delta[pl] * conversion; //temps = distance * inverse de la vitesse
    ld_copy = ld;
    ld_copy.t = ld.t - tau;
    ld_copy.t0 = ld.t0 - tau;

    //Deuxième itération (sans recalculer les coordonnées du Soleil)
    SysSol_LonLatRay(ld_copy, syso, pl);
    SySol_MoonNode(ld, syso);
    SySol_ObqEcliptic(ld_copy, syso);
    SySol_CREGplanet(ld_copy, syso, creg, pl);

    //Calcul final des coordonnées équatoriales
    syso.dp[pl] = Math.asin(creg.wp[pl] / syso.delta[pl]);
    syso.ap[pl] = Math.atan(creg.vp[pl] / creg.up[pl]);
    if (creg.up[pl] < 0)
      syso.ap[pl] = syso.ap[pl] + pi;
    else
    {
      if (syso.ap[pl] < 0) syso.ap[pl] = syso.ap[pl] + dpi;
    }
  }

  /////////////////////////////////////////////////////////////////////////////
  //Calcul des coordonnées solaires
  syso.dp[0] = Math.asin(sin(syso.oba) * sin(syso.phiapp));
  syso.ap[0] = Math.atan(cos(syso.oba) * sin(syso.phiapp) / cos(syso.phiapp));
  if (cos(syso.phiapp) < 0)
    syso.ap[0] = syso.ap[0] + pi;
  else
  {
    if (syso.ap[0] < 0) syso.ap[0] = syso.ap[0] + dpi;
  }

  /////////////////////////////////////////////////////////////////////////////
  //Calcul des coordonnées lunaires
  SySol_MoonElements(ld, syso);
  SysSol_LonLatRay(ld, syso, 9);

  //Correction de la longitude due à la nutation
  SySol_ObqEcliptic(ld, syso);
  SySol_MeanLongitude(ld, syso, 0);
  SySol_MeanAnomaly(ld, syso, 0);
  re = syso.lon[9] + ((-17.233+0.017*ld.t)*sin(syso.o) - 1.273*sin(2*syso.l0))*ic1rd;

  //On en déduit les coordonnées équatoriales géocentriques de la Lune
  syso.dp[9] = Math.asin(cos(syso.lat[9])*sin(re)*sin(syso.oba)+sin(syso.lat[9])*cos(syso.oba));
  syso.ap[9] = cos(syso.lat[9])*sin(re)*cos(syso.oba)-sin(syso.lat[9])*sin(syso.oba);
  syso.ap[9] = Math.atan(syso.ap[9]/(cos(syso.lat[9])*cos(re)));
  if (cos(syso.lat[9])*cos(re) < 0)
    syso.ap[9] = syso.ap[9] + pi;
  else
  {
    if (syso.ap[9] < 0) syso.ap[9] = syso.ap[9] + dpi;
  }
}


// Objectif: Fonction de branchement pour le calcul des coordonnées
//           équatoriales d'une planète, du Soleil ou de la Lune
// Remarques: rien n'est à calculer au préalable
function SySol_AD(ld, syso, pl)
{
  switch (pl)
  {
    case 0:
      SySol_ADsun(ld, syso);
      break;
    case 9:
      SySol_ADmoon(ld, syso);
      break;
    default:
      SySol_ADplanet(ld, syso, pl);
  }
}
/*
// Objectif: Fonction de transformation des coordonnées équatoriales
//           géocentriques des planètes en coordonnées topocentriques
// Remarques: calculer au préalable les coordonnées équatoriales géocentriques
//            des planètes, de la Lune et du Soleil
funciton SySol_Topocentric(ld, pu, syso)
{
  var pl;		//int
  var lat, u, rcosp, rsinp;	//double
  var cosdelta, sinomega, h, hp, qcosdpcoshp, qcosdpsinhp;	//double

  lat = pu.lat*rd;
  u = Math.atan(bsa * sin(lat)/cos(lat));
  rcosp = cos(u) + pu.alti/rayt*ld.coslatast;    //rhô.cos(phi')
  rsinp = bsa*sin(u) + pu.alti/rayt*ld.sinlatast;  //rhô.sin(phi')
  for (pl=0; pl<=9; pl++)
  {
    if (pl==0) SySol_Ray0(ld, syso);
    if (pl==9)
      sinomega = sin(1/syso.r[9]);
    else
      sinomega = sin(rayt/ua/syso.delta[pl]);
    h = ld.tslrad - syso.ap[pl];
    cosdelta = cos(syso.dp[pl]);
    qcosdpcoshp = cosdelta*cos(h)-rcosp*sinomega;
    qcosdpsinhp = cosdelta*sin(h);
    hp = Math.atan(qcosdpsinhp/qcosdpcoshp);
    if (qcosdpcoshp<0.0) hp = hp + pi;
    syso.dp[pl] = Math.atan(sin(hp)*(sin(syso.dp[pl])-rsinp*sinomega)/qcosdpsinhp);
    syso.ap[pl] = ld.tslrad - hp;
    if (syso.ap[pl]>dpi)
      syso.ap[pl]=syso.ap[pl]-dpi;
    else
      if (syso.ap[pl]<0.0) syso.ap[pl]=syso.ap[pl]+dpi;
  }
}
*/
function pl_diameter(pl)
{
	switch (pl)
	{
		case 0: return 1392000e3;
		case 1: return 4878e3;
		case 2: return 12104e3;
		case 3: return 6794e3;
		case 4: return 142796e3;
		case 5: return 120000e3;
		case 6: return 51200e3;
		case 7: return 48600e3;
		case 8: return 2200e3;
		case 9: return 3476e3;
	}
}

// Objectif: Fonction de calcul des diamètres apparents des planètes, de la Lune
//           et du Soleil
// Remarques: calculer au préalable les distances séparant la Terre des
//            planètes, de la Lune et du Soleil
function SySol_Diameters(ld, syso)
{
	var pl;	//int

	for (pl=0; pl<9; pl++)
	{
		syso.dapp[pl] = 2.0*Math.atan(pl_diameter(pl)/2.0/(ua*syso.delta[pl]));
	}
	syso.dapp[9] = 2.0*Math.atan(pl_diameter(9)/2.0/(rayt*syso.delta[9]));
}


// Objectif: Fonction de calcul de la magnitude, de la phase, de l'élongation
//           et de la fraction illuminée pour les planètes et la Lune
// Remarques: calculer au préalable les distances séparant la Terre des
//            planètes, leur distance au Soleil, leurs longitude et latitude
//            héliocentriques
function SySol_CalculsSupplementaires(ld, syso, pl)
{
  var re, lgrd, phu;	//double

  /////////////////////////////////////////////////////////////////////////////
  //Angle d'élongation de la planète
  if (pl==9)
  {
    SySol_Ray0(ld, syso);
    SySol_RealLonSun(ld, syso);        //Longitude vraie du Soleil
    syso.elongation[9] = Math.acos(cos(syso.lat[9])*cos(syso.lon[9]-syso.phi));
    re = modulo(syso.lon[9]-syso.phi-pi,dpi);
    if (re>pi)
      syso.elongation[9] = -syso.elongation[9];
    syso.delta[9] = syso.r[9];
  }
  else
    if (pl!=0)
    {
      SySol_Ray0(ld, syso);
      syso.elongation[pl] = Math.acos((carre(syso.r[0])+carre(syso.delta[pl])-carre(syso.r[pl]))/(2*syso.r[0]*syso.delta[pl]));
      re = modulo(syso.lon[pl]-syso.phi-pi,dpi);
      if (re>pi)
        syso.elongation[pl] = -syso.elongation[pl];
    }

  /////////////////////////////////////////////////////////////////////////////
  //Angle de phase de la planète
  if (pl==9)
    syso.phase[9] = pi-Math.abs(syso.elongation[9])-Math.asin(syso.r[9]*rayt/ua/syso.r[0]*sin(syso.elongation[9]));
  else
    syso.phase[pl] = Math.acos((carre(syso.r[pl])+carre(syso.delta[pl])-carre(syso.r[0]))/(2*syso.r[pl]*syso.delta[pl]));

  /////////////////////////////////////////////////////////////////////////////
  //Fraction du disque illuminé en %
  if (pl>0)
    syso.fraction_illuminee[pl] = (1+cos(syso.phase[pl]))*50;

  /////////////////////////////////////////////////////////////////////////////
  //Magnitude de la planète
  if ((pl>0))
  {
    lgrd = Math.log(syso.r[pl]*syso.delta[pl])/Math.log(10);
    phu = syso.phase[pl]*dr;
    switch (pl)
    {
      case 1: syso.magnitude[1] = 1.16+5*lgrd+0.02838*(phu-50)+0.0001023*carre(phu-50);break;
      case 2: syso.magnitude[2] = -4+5*lgrd+0.01322*phu+0.00000004247*carre(phu)*phu;break;
      case 3: syso.magnitude[3] = -1.3+5*lgrd+0.01486*phu;break;
      case 4: syso.magnitude[4] = -8.93+5*lgrd;break;
      case 5: syso.magnitude[5] = -8.68+5*lgrd;break;   // Et les Anneaux.....
      case 6: syso.magnitude[6] = -6.85+5*lgrd;break;
      case 7: syso.magnitude[7] = -7.05+5*lgrd;break;
      case 8: syso.magnitude[8] = -0.14+5*lgrd;break;
      case 9: syso.magnitude[9] = 0+0*lgrd;break;
    }
  }
  else
  {
      syso.magnitude[0] = -26.7;
  }
}

// Calcule la parallaxe d'un objet du système solaire
function CalcParallaxe(ld, syso, pl)
{
	if (pl==9)
		return Math.asin(1/syso.r[9]);
	else
		return rayt/ua/syso.delta[pl]; // ArcSinus Confondu avec l'angle
}

function MeridPl(ld, syso, pl)
{
	var j;				//Byte;
	var t2, tu;		//Double;
	var ld_copy;		//LocalData
	
	ld_copy = new sLocalData();
	ld_copy = ld;			//¤¤¤
	tu = 12;
	for (j=1; j<=4; j++)
	{
		ld.t = ld.t0 + tu/24/36525;
		SySol_AD(ld, syso, pl);
		t2 = tu;
		tu = modulo((ld.lonast + syso.ap[pl])*dr/15 - ld.tsl0, 24);
/*		if (tu<0)
			tu += 24;*/
		tu *= invSunMeanDay;
	}
	ld = ld_copy;
	if ((Math.abs(tu-t2)>13.6))
		return 99;
	else
	{
		if (tu<0)
			return tu+24;
		else
			return tu;
	}
}

function LCpl(ld, syso, pl, AngleH, hauteur)
{
	var j;	//byte
	var tu,tt,u,x,y,az,ah,sinh0,cosdp,sindp;	//Double

	tu=12;
	for (j=1; j<=4; j++)
	{
		ld.t = ld.t0 + tu/24/36525;
		SySol_AD(ld, syso, pl);
		sindp = sin(syso.dp[pl]);
		cosdp = Math.sqrt(1-carre(sindp));
		sinh0 = sin(hauteur*rd+CalcParallaxe(ld, syso, pl));
		u = (sinh0-sin(ld.latast)*sindp)/cos(ld.latast)/cosdp;
		if (Math.abs(u)>1)
		{
			return 99;
		}
		else
		{
			ah = Math.acos(u);
			tu = modulo((ld.lonast+AngleH*ah+syso.ap[pl])*dr/15-ld.tsl0,24)*invSunMeanDay;
			if (j==1)
				tt = tu;
			else
			if (Math.abs(tu-tt)>12)
				 return 99;
		}
	}
	return tu;
}


function LMC(ld, syso, pl, type)
{
	switch (type)
	{
	    	case 0: return LCpl(ld,syso,pl,-1,-18);
		case 1: return LCpl(ld,syso,pl,-1,-12);
		case 2: return LCpl(ld,syso,pl,-1,-6);
		//case 3: return LCpl(ld,syso,pl,-1,-0.61);
		case 3: return LCpl(ld,syso,pl,-1,-0.833);
		case 4: return MeridPl(ld,syso,pl);
		//case 5: return LCpl(ld,syso,pl,1,-0.61);
		case 5: return LCpl(ld,syso,pl,1,-0.833);
		case 6: return LCpl(ld,syso,pl,1,-6);
		case 7: return LCpl(ld,syso,pl,1,-12);
		case 8: return LCpl(ld,syso,pl,1,-18);
	}
}


//COMMUN**************************************************************************************
function sin(x)
{
	return Math.sin(x);
}

function cos(x)
{
	return Math.cos(x);
}

function carre(x)
{
	return x*x;
}

function cube(x)
{
	return x*x*x;
}

function modulo(d, e)
{
	m = d-e*Math.ceil(d/e);
	if (m<0)
		return m+e;
	else
		return m;
}

function decisexa(Tp)
{
	AbsTp = Math.abs(Tp);   //Le résultat ne tient compte que de la valeur absolue
	this.h = Math.floor(AbsTp);
	this.m = Math.floor((AbsTp-this.h)*60);
	this.s = Math.floor((AbsTp-this.h-this.m/60)*3600);
}

function dms(x)
{
	sexa = new decisexa(x);
	s = '' + sexa.h + '°' + sexa.m + "'" + sexa.s + '"';
	if (x<0)
		return '-'+s;
	else
		return s;
}

function hms(x)
{
	sexa = new decisexa(x);
	s = '' + sexa.h + 'h' + sexa.m + 'm' + sexa.s + 's';
	if (x<0)
		return '-'+s;
	else
		return s;
}

//-->