// 事件窗口深挖：CEventWindow RTTI/vftable + lambda 追踪 + option 点击路径
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.symbol.Reference;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

public class EvtWin extends GhidraScript {

    List<Long> findPattern(byte[] pat) throws Exception {
        List<Long> hits = new ArrayList<>();
        Address start = currentProgram.getMinAddress();
        Address end = currentProgram.getMaxAddress();
        while (true) {
            Address a = currentProgram.getMemory().findBytes(start, end, pat, null, true, monitor);
            if (a == null) {
                break;
            }
            hits.add(a.getOffset());
            if (hits.size() > 64) {
                break;
            }
            start = a.add(1);
        }
        return hits;
    }

    String readCStr(Address a, int max) {
        StringBuilder sb = new StringBuilder();
        try {
            for (int i = 0; i < max; i++) {
                int b = getByte(a.add(i)) & 0xff;
                if (b == 0) {
                    break;
                }
                sb.append((char) b);
            }
        } catch (Exception e) {
        }
        return sb.toString();
    }

    void colHunt(long tdVA, String label) throws Exception {
        println("==== COL hunt for " + label + "  TD=0x" + Long.toHexString(tdVA) + " ====");
        long imgBase = currentProgram.getImageBase().getOffset();
        long rva = tdVA - imgBase;
        byte[] pat = new byte[4];
        for (int i = 0; i < 4; i++) {
            pat[i] = (byte) ((rva >>> (8 * i)) & 0xff);
        }
        List<Long> hits = findPattern(pat);
        println("  pat=" + String.format("%02x %02x %02x %02x", pat[0], pat[1], pat[2], pat[3]) + "  hits=" + hits.size());
        for (long h : hits) {
            long colVA = h - 0xC;
            try {
                int sig = getInt(toAddr(colVA));
                if (sig != 1) {
                    continue;
                }
                int off = getInt(toAddr(colVA + 4));
                int cd = getInt(toAddr(colVA + 8));
                int tdRva = getInt(toAddr(colVA + 0xC));
                int clsRva = getInt(toAddr(colVA + 0x10));
                int selfRva = getInt(toAddr(colVA + 0x14));
                String tdName = readCStr(toAddr(imgBase + (tdRva & 0xffffffffL) + 0x10), 120);
                println("  COL @0x" + Long.toHexString(colVA) + " sig=1 off=" + off + " cd=" + cd
                        + " tdRva=0x" + Integer.toHexString(tdRva) + " selfRva=0x" + Integer.toHexString(selfRva));
                println("    TD name: " + tdName);
                byte[] p8 = new byte[8];
                long colVa = colVA;
                for (int i = 0; i < 8; i++) {
                    p8[i] = (byte) ((colVa >>> (8 * i)) & 0xff);
                }
                List<Long> refs = findPattern(p8);
                println("    qword-pointers to COL (0x" + Long.toHexString(colVa) + "): " + refs.size());
                for (long r : refs) {
                    long vt = r + 8;
                    println("    vftable candidate @0x" + Long.toHexString(vt));
                    for (int k = 0; k < 8; k++) {
                        long fn = getLong(toAddr(vt + 8L * k));
                        if (fn < 0x140000000L || fn > 0x150000000L) {
                            break;
                        }
                        Function f = getFunctionContaining(toAddr(fn));
                        println("      [" + k + "] 0x" + Long.toHexString(fn) + "  "
                                + (f != null ? f.getName() : "?"));
                    }
                    println("    -- code refs to vftable 0x" + Long.toHexString(vt) + " (construction sites) --");
                    Set<Long> fseen = new LinkedHashSet<>();
                    List<Long> faddrs = new ArrayList<>();
                    for (Reference vr : getReferencesTo(toAddr(vt))) {
                        Function vf = getFunctionContaining(vr.getFromAddress());
                        long fe = vf != null ? vf.getEntryPoint().getOffset() : 0;
                        println("      " + vr.getReferenceType() + " from " + vr.getFromAddress()
                                + " in " + (vf != null ? vf.getName() + "@0x" + Long.toHexString(fe) : "?"));
                        if (vf != null && fseen.add(fe)) {
                            faddrs.add(fe);
                        }
                    }
                    for (long fe : faddrs) {
                        decompileFn(fe, 130);
                    }
                }
            } catch (Exception e) {
                println("    (parse fail @0x" + Long.toHexString(h) + " : " + e + ")");
            }
        }
    }

    void decompileFn(long va, int cap) {
        Function f = getFunctionContaining(toAddr(va));
        if (f == null) {
            println("  (no function @0x" + Long.toHexString(va) + ")");
            return;
        }
        println("==== decompile " + f.getName() + " @0x" + Long.toHexString(f.getEntryPoint().getOffset()) + " (cap " + cap + ") ====");
        try {
            DecompInterface dec = new DecompInterface();
            dec.openProgram(currentProgram);
            DecompileResults res = dec.decompileFunction(f, 90, monitor);
            if (res != null && res.decompileCompleted()) {
                String[] lines = res.getDecompiledFunction().getC().split("\n");
                for (int i = 0; i < Math.min(lines.length, cap); i++) {
                    println("  " + lines[i]);
                }
                if (lines.length > cap) {
                    println("  ... (" + (lines.length - cap) + " more lines)");
                }
            } else {
                println("  (decompile failed)");
            }
            dec.dispose();
        } catch (Exception e) {
            println("  (decompile error " + e + ")");
        }
    }

    void asmWindow(long va, int before, int after) {
        println("==== asm around 0x" + Long.toHexString(va) + " ====");
        Instruction ins = getInstructionAt(toAddr(va));
        if (ins == null) {
            Function f = getFunctionContaining(toAddr(va));
            if (f != null) {
                Address a = f.getBody().getMinAddress();
                Address end = f.getBody().getMaxAddress();
                while (a != null && a.compareTo(end) <= 0) {
                    Instruction t = getInstructionAt(a);
                    if (t == null) {
                        break;
                    }
                    if (t.getAddress().getOffset() <= va && va <= t.getMaxAddress().getOffset()) {
                        ins = t;
                        break;
                    }
                    Instruction n = t.getNext();
                    a = (n == null) ? null : n.getAddress();
                }
            }
        }
        if (ins == null) {
            println("  (no instruction)");
            return;
        }
        for (int i = 0; i < before; i++) {
            Instruction p = ins.getPrevious();
            if (p == null) {
                break;
            }
            ins = p;
        }
        for (int i = 0; i < before + after; i++) {
            println("   " + ins.getAddress() + "  " + ins);
            ins = ins.getNext();
            if (ins == null) {
                break;
            }
        }
    }

    void callersOf(long va, int maxPrint, int cap) {
        println("==== callers of 0x" + Long.toHexString(va) + " ====");
        Set<Long> seen = new LinkedHashSet<>();
        List<Long> addrs = new ArrayList<>();
        for (Reference r : getReferencesTo(toAddr(va))) {
            if (!r.getReferenceType().isCall() && !r.getReferenceType().isJump()) {
                continue;
            }
            Function f = getFunctionContaining(r.getFromAddress());
            long fe = f != null ? f.getEntryPoint().getOffset() : 0;
            println("  " + r.getReferenceType() + " from " + r.getFromAddress()
                    + " in " + (f != null ? f.getName() + "@0x" + Long.toHexString(fe) : "?"));
            if (f != null && seen.add(fe)) {
                addrs.add(fe);
            }
        }
        for (long fe : addrs) {
            if (maxPrint-- <= 0) {
                break;
            }
            decompileFn(fe, cap);
        }
    }

    @Override
    public void run() throws Exception {
        long imgBase = currentProgram.getImageBase().getOffset();
        println("imageBase=0x" + Long.toHexString(imgBase));

        println("==== dump around 0x1428c59b0 ====");
        for (long a = 0x1428c5990L; a < 0x1428c5a10L; a += 16) {
            StringBuilder hex = new StringBuilder();
            StringBuilder asc = new StringBuilder();
            for (int i = 0; i < 16; i++) {
                int b = getByte(toAddr(a + i)) & 0xff;
                hex.append(String.format("%02x ", b));
                asc.append(b >= 32 && b < 127 ? (char) b : '.');
            }
            println("  " + Long.toHexString(a) + ": " + hex + " |" + asc + "|");
        }

        // 1) lambda RTTI -> COL -> vftable -> code refs
        colHunt(0x1428c59b0L, "lambda (string addr as-is)");
        colHunt(0x1428c59a0L, "lambda (TD assumed at -0x10)");

        // 2) CEventWindow class RTTI
        List<Long> cew = findPattern(".?AVCEventWindow@@".getBytes("US-ASCII"));
        println("==== 'CEventWindow@@' raw hits: " + cew.size() + " ====");
        for (long h : cew) {
            println("  @0x" + Long.toHexString(h) + " : " + readCStr(toAddr(h - 16), 160));
        }
        if (!cew.isEmpty()) {
            colHunt(cew.get(0) - 0x10, "CEventWindow class");
        }

        // 3) event option click telemetry helpers -> callers (real handlers)
        callersOf(0x141291c80L, 3, 70);
        callersOf(0x141291ce0L, 3, 70);

        // 4) option button builder + callers
        callersOf(0x14107b1d0L, 2, 60);
        asmWindow(0x14107b228L, 24, 40);
        asmWindow(0x14107a3b4L, 20, 40);

        // 5) decompile the two event-window GUI functions
        decompileFn(0x1410793a0L, 150);
        decompileFn(0x14107a180L, 150);

        println("==== done ====");
    }
}
