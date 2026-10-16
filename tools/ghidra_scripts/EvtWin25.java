// EvtWin25: CSelectEventOptionCommand —— 找类 TD/COL/vtable/Execute 与构造点
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

public class EvtWin25 extends GhidraScript {

    List<Long> findPattern(byte[] pat) throws Exception {
        List<Long> hits = new ArrayList<>();
        int keep = pat.length - 1;
        for (MemoryBlock blk : currentProgram.getMemory().getBlocks()) {
            if (!blk.isInitialized()) {
                continue;
            }
            long start = blk.getStart().getOffset();
            long end = blk.getEnd().getOffset();
            int chunk = 1 << 22;
            byte[] buf = new byte[chunk];
            byte[] carry = new byte[0];
            long pos = start;
            outer:
            while (pos <= end) {
                int want = (int) Math.min(chunk, end - pos + 1);
                int got;
                try {
                    got = blk.getBytes(toAddr(pos), buf, 0, want);
                } catch (Exception e) {
                    break;
                }
                if (got <= 0) {
                    break;
                }
                byte[] data = new byte[carry.length + got];
                System.arraycopy(carry, 0, data, 0, carry.length);
                System.arraycopy(buf, 0, data, carry.length, got);
                long baseVa = pos - carry.length;
                for (int i = 0; i + pat.length <= data.length; i++) {
                    boolean ok = true;
                    for (int j = 0; j < pat.length; j++) {
                        if (data[i + j] != pat[j]) {
                            ok = false;
                            break;
                        }
                    }
                    if (ok) {
                        hits.add(baseVa + i);
                        if (hits.size() > 200) {
                            break outer;
                        }
                    }
                }
                if (got < want) {
                    break;
                }
                pos += got;
                int k = Math.min(keep, data.length);
                carry = Arrays.copyOfRange(data, data.length - k, data.length);
            }
        }
        return hits;
    }

    String readCStr(long va, int max) {
        StringBuilder sb = new StringBuilder();
        try {
            for (int i = 0; i < max; i++) {
                int b = getByte(toAddr(va + i)) & 0xff;
                if (b == 0) {
                    break;
                }
                if (b < 32 || b > 126) {
                    break;
                }
                sb.append((char) b);
            }
        } catch (Exception e) {
        }
        return sb.toString();
    }

    void dumpVtable(long vt, int n) {
        println("    vftable @0x" + Long.toHexString(vt));
        for (int k = 0; k < n; k++) {
            try {
                long fn = getLong(toAddr(vt + 8L * k));
                if (fn < 0x140000000L || fn > 0x150000000L) {
                    break;
                }
                Function f = getFunctionContaining(toAddr(fn));
                println("      [" + k + "] 0x" + Long.toHexString(fn) + "  " + (f != null ? f.getName() : "?"));
            } catch (Exception e) {
                break;
            }
        }
    }

    void colHunt(long tdVA, String label) throws Exception {
        println("==== COL hunt: " + label + "  TD=0x" + Long.toHexString(tdVA) + " ====");
        long imgBase = currentProgram.getImageBase().getOffset();
        long rva = tdVA - imgBase;
        byte[] pat = new byte[4];
        for (int i = 0; i < 4; i++) {
            pat[i] = (byte) ((rva >>> (8 * i)) & 0xff);
        }
        List<Long> hits = findPattern(pat);
        println("  rva-pat hits=" + hits.size());
        Set<Long> cols = new LinkedHashSet<>();
        for (long h : hits) {
            long colVA = h - 0xC;
            try {
                if (getInt(toAddr(colVA)) != 1) {
                    continue;
                }
                int tdRva = getInt(toAddr(colVA + 0xC));
                if ((tdRva & 0xffffffffL) != rva) {
                    continue;
                }
                cols.add(colVA);
            } catch (Exception e) {
            }
        }
        println("  valid COLs: " + cols.size());
        for (long colVA : cols) {
            byte[] p8 = new byte[8];
            for (int i = 0; i < 8; i++) {
                p8[i] = (byte) ((colVA >>> (8 * i)) & 0xff);
            }
            List<Long> refs = findPattern(p8);
            println("    COL @0x" + Long.toHexString(colVA) + "  qword-refs=" + refs.size());
            for (long r : refs) {
                long vt = r + 8;
                dumpVtable(vt, 8);
                println("    -- vtable refs（构造点/使用者） --");
                int dn = 0;
                Set<Long> done = new LinkedHashSet<>();
                for (Reference vr : getReferencesTo(toAddr(vt))) {
                    Function vf = getFunctionContaining(vr.getFromAddress());
                    if (vf == null) {
                        continue;
                    }
                    long fe = vf.getEntryPoint().getOffset();
                    println("      ref from 0x" + Long.toHexString(vr.getFromAddress().getOffset())
                            + " in " + vf.getName() + "@0x" + Long.toHexString(fe));
                    if (done.add(fe) && dn++ < 2) {
                        decompileFn(fe, 90);
                    }
                }
            }
        }
    }

    void decompileFn(long va, int cap) {
        Function f = getFunctionContaining(toAddr(va));
        if (f == null) {
            return;
        }
        println("    ==== decompile " + f.getName() + " (cap " + cap + ") ====");
        try {
            DecompInterface dec = new DecompInterface();
            dec.openProgram(currentProgram);
            DecompileResults res = dec.decompileFunction(f, 120, monitor);
            if (res != null && res.decompileCompleted()) {
                String[] lines = res.getDecompiledFunction().getC().split("\n");
                for (int i = 0; i < Math.min(lines.length, cap); i++) {
                    println("      " + lines[i]);
                }
            }
            dec.dispose();
        } catch (Exception e) {
        }
    }

    @Override
    public void run() throws Exception {
        List<Long> hits = findPattern("CSelectEventOptionCommand".getBytes("US-ASCII"));
        println("'CSelectEventOptionCommand' 命中 " + hits.size() + " 处");
        Set<Long> tdNames = new LinkedHashSet<>();
        for (long h : hits) {
            String ctx = readCStr(h - 40, 140);
            println("  @0x" + Long.toHexString(h) + " : ..." + ctx);
            if (ctx.contains(".?AVCSelectEventOptionCommand@@")) {
                long tdStart = h - 40 + ctx.indexOf(".?AVCSelectEventOptionCommand@@");
                tdNames.add(tdStart);
            }
        }
        for (long td : tdNames) {
            colHunt(td, "class TD");
        }
        println("==== done ====");
    }
}
