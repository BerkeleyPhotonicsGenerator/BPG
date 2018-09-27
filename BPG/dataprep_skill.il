
printf("\n\n\nDefining skill dataprep functions. \n\n\n")

;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
; Flatten
;
; This procedure takes as input a one dbObject (db adress) and flattens it.
;
; Arguments
; ---------
;   DbObject :
;       db address of the cell to flatten, for example DbObject = pcCellView, or DbObject = dbCreateParamInst( .... )
;
; Returns
; -------
;   t if successful, nil if there was a problem.
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

procedure( Flatten(DbObject)
	let(
	    (
            TOrNil
            Inst
            Mosaic
		)

		; initialization.
	    TOrNil = t

        ; Flattening instances.
        foreach( Inst DbObject~>instances
            when(Inst~>objType == "inst"
                TOrNil = dbFlattenInst(Inst 32 t nil nil) &&  TOrNil  ; 32 is the maximum value possible.
            )
        ) ; end foreach.

        ; Flattening mosaics.
        foreach( Mosaic DbObject~>mosaicss
            when( Mosaic~>objType == "mosaic"
                TOrNil = dbFlattenInst(Mosaic 32 t nil nil) &&  TOrNil
            )
        ) ; end foreach.

        ; Giving error message if necessary:
	    if(TOrNil != t
		    printf("Error in 0ProcedureFlatten while flattening %L.\n" list(DbObject) )
	    ) ; end if.

        ; Returning result:
	    TOrNil	; procedure returns this value

	) ; end of body of code (let)
) ; end of procedure definition



;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
; RemoveConsecutiveDoubles
;
; Gets rid of sequential points that are the same
;
; Arguments
; ---------
;   CoordList :
;       List of coordinate points in the polygon
;
;
; Returns
; -------
;   NewPoints :
;       List of coordinate points with consecutive duplicates removed
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

procedure( RemoveConsecutiveDoubles(CoordList)
    let(
        (
		    NewPoints
		    PointCheck
		)

        ; initialize points to keep
        NewPoints = nil
        PointCheck = nil

        ; loop through to make sure there are not sequential redundant points
        foreach(Point CoordList
            if(Point!=PointCheck
            then
                NewPoints=cons(Point NewPoints)
            )
            PointCheck=Point
        )
        reverse(NewPoints)
	) ; end let
) ; end procedure




;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
; Manh
;
; Converts a list of coordinates of a polygon into the best-fit polygon made of orthogonal (Manhattan) segments.
; The new polygon is unique (it does not depend on the order of the input points) and is larger than the original.
;
; Arguments
; ---------
;   PolygonPoints :
;       List of coordinate points in the polygon
;   ManhGridSize :
;       Grid on which Manhattan points should be placed
;
; Returns
; -------
;   PointsOrthogonalRoundedUnique :
;       Manhattanized polygon points list
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

procedure( Manh(PolygonPoints
                ManhGridSize
                )
	let(
	    (
            PolygonPointsTemp
            Point		IndPoint
            XInside 	YInside
            ThisPoint 	NextPoint
            DeltaX		DeltaY
            NumPointsToAdd IndNewPoint
            X0			Y0
            StepX 		StepY
            VectorialProduct1 VectorialProduct2
            PointsOrthogonal
            PointsOrthogonalRounded
            PointsOrthogonalRoundedUnique
		)

        if( debug
        then
            printf("Manh\n")
        )

        ; Snap original coordinates to Manhattan grid by rounding
        PolygonPointsTemp = nil ; initialization.
        foreach(Point PolygonPoints
            PolygonPointsTemp = cons(
                list(
                    ManhGridSize * round(xCoord(Point)/ManhGridSize)
                    ManhGridSize * round(yCoord(Point)/ManhGridSize)
                )
                PolygonPointsTemp
            )
        ) ; end foreach.
        PolygonPoints = PolygonPointsTemp

if( debug
        then
            printf("155\n")
        )

        ; Adding last point to the beginning to ensure the polygon is closed
	    PolygonPoints = cons(
	        nth(length(PolygonPoints)-1 PolygonPoints)
	        PolygonPoints
	    )

        ; Determining the coordinate of a point which is certainly inside the convex envelope of the polygon
        ; (a kind of "center-of-mass")
		XInside = 0.0
		YInside = 0.0
		foreach(Point PolygonPoints
			XInside = XInside + xCoord(Point)
			YInside = YInside + yCoord(Point)
		)
		XInside = XInside / length(PolygonPoints)
		YInside = YInside / length(PolygonPoints)

		; printf("Point INSIDE the shape x,y =  %L : \n" list(XInside YInside))

        ; Scan all the points of the original list and add points in-between.
        ; Initialize the new list of points with the first original point.
		PointsOrthogonal = list(car( PolygonPoints ))
		PolygonPointsLoop = PolygonPoints

		; Loop over every point in the shape.
		for(IndPoint 0 length(PolygonPoints)-1
		    ; printf("This is a Point in FIRST LOOP %L : \n" nth(i Shape~>points))
			ThisPoint = car(PolygonPointsLoop)
			NextPoint = cadr(PolygonPointsLoop)
			if(NextPoint==nil then
				NextPoint=ThisPoint
			)

			DeltaX = xCoord(NextPoint)-xCoord(ThisPoint)
			DeltaY = yCoord(NextPoint)-yCoord(ThisPoint)
			PointsOrthogonal = cons( ThisPoint PointsOrthogonal)

			if( DeltaX == 0.0 || DeltaY == 0.0
			then
			    ; ThisPoint and NextPoint are already on an orthogonal grid.
				; printf("This point has orthogonal neighbour %L : \n" ThisPoint)
				PointsOrthogonal = cons( NextPoint PointsOrthogonal)
			else
			    ; ThisPoint and NextPoint are NOT on an orthogonal grid.
			    ; GENERAL RULE FOR DETERMINING A UNIQUE DISCRETIZATION:
			    ; X IS INCREMETED BEFORE Y IN EVERY AMBIGUOUS CASE (E.G. 45DEG)
				if( abs(DeltaX) > abs(DeltaY)
				then
				    ; the segment to approximate is closer to the x-axis than the y-axis:
					NumPointsToAdd = abs(round(DeltaY/ManhGridSize))
					X0 = xCoord(ThisPoint)
					Y0 = yCoord(ThisPoint)
					for( IndNewPoint 1 NumPointsToAdd
						StepX = round(DeltaY/abs(DeltaY)) * DeltaX/DeltaY * ManhGridSize
						StepY = StepX * DeltaY / DeltaX
						VectorialProduct1 = StepX * (YInside-yCoord(ThisPoint)) - StepY * (XInside-xCoord(ThisPoint))
						; if VP1 positive, the center if the shape is on the left
						VectorialProduct2 = StepX * 0.0 - StepY * StepX
						; if VP2 positive the vector ( StepX, 0.0) is on the left too
						; If both are positive, incrementing in X first is the bad choice:
						if( VectorialProduct1 * VectorialProduct2 < 0
						then
						    ; increment X first
							PointsOrthogonal = cons(list( X0 + StepX Y0         ) PointsOrthogonal)
							PointsOrthogonal = cons(list( X0 + StepX Y0 + StepY ) PointsOrthogonal)
						else
						    ; increment Y first
							PointsOrthogonal = cons(list( X0         Y0 + StepY ) PointsOrthogonal)
							PointsOrthogonal = cons(list( X0 + StepX Y0 + StepY ) PointsOrthogonal)
						)
						X0 = X0 + StepX
						Y0 = Y0 + StepY
					; printf("pos 1 list: %L %L \n" list(length(PointsOrthogonal)) list(NumPointsToAdd))
					)
				else
				    ; the segment to approximate is closer to the y-axis than the x-axis:
					NumPointsToAdd = abs(round(DeltaX/ManhGridSize))
					; printf("number of points %L \n" list(NumPointsToAdd))
					X0 = xCoord(ThisPoint)
					Y0 = yCoord(ThisPoint)
					for(IndNewPoint 1 NumPointsToAdd
						StepY = round(DeltaX/abs(DeltaX)) * DeltaY/DeltaX * ManhGridSize
						StepX = StepY * DeltaX / DeltaY
						VectorialProduct1 = StepX * (YInside-yCoord(ThisPoint)) - StepY * (XInside-xCoord(ThisPoint))
						; if VP1 positive, the center if the shape is on the left
						VectorialProduct2 = StepX * 0.0 - StepY * StepX
						; if VP2 positive the vector ( StepX, 0.0) is on the left too
						; If both are positive, incrementing in X first is the bad choice:
						if( VectorialProduct1 * VectorialProduct2 < 0
						then
						    ; increment X first
							PointsOrthogonal = cons(list( X0 + StepX Y0         ) PointsOrthogonal)
							PointsOrthogonal = cons(list( X0 + StepX Y0 + StepY ) PointsOrthogonal)
						else
						    ; increment Y first
							PointsOrthogonal = cons(list( X0         Y0 + StepY ) PointsOrthogonal)
							PointsOrthogonal = cons(list( X0 + StepX Y0 + StepY ) PointsOrthogonal)
						)
						X0 = X0 + StepX
						Y0 = Y0 + StepY
					; printf("pos 2 list: %L %L \n" list(length(PointsOrthogonal)) list(NumPointsToAdd))
					)
					; printf("pos 3 list: %L %L %L\n" list(length(PointsOrthogonal)) list(NumPointsToAdd) PointsOrthogonal)
					; printf("OTHER case!!\n")
				)
			)
			PolygonPointsLoop = cdr(PolygonPointsLoop)
		) ; End for IndPoint

        ; Snapping final coordinates to grid (by rounding):
	    PointsOrthogonalRounded = nil
        foreach(Point PointsOrthogonal
            PointsOrthogonalRounded = cons(
                list(
                    ManhGridSize * round(xCoord(Point)/ManhGridSize)
                    ManhGridSize * round(yCoord(Point)/ManhGridSize)
                )
                PointsOrthogonalRounded)
        ) ; end foreach.

        ; Removing double points:
	    PointsOrthogonalRoundedUnique = RemoveConsecutiveDoubles(PointsOrthogonalRounded)

        ; Returning result:
		PointsOrthogonalRoundedUnique
	) ; end of body of code (let)
) ; end of procedure



;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
; CoordPrep
;
; This procedure takes as input an arbitrarily large coordinate list and returns a list of coordinate lists with maximum
; 1000 points each. Notice that the returned quantity has a list depth +1. This procedure is used to create sub-polygons
; with less than 4000 points (more than that is not allowed in SKILL).
;
; Arguments
; ---------
;   PolygonPoints :
;       List of coordinate points in the polygon
;   GridSize : Optional = GlobalGridSize
;       Grid on which points should be placed
;
; Returns
; -------
;   SubPolygons :
;       List of coordinate lists with fewer than 1000 points each
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

procedure( CoordPrep(PolygonPoints
                     @optional (GridSize GlobalGridSize)
                     )
	let(
	    (
		SubPolygonXPitch
		XMin
		XMax
		YMin
		YMax
		PolygonPoint
		IndPolygonPoint
		TempPolygonPoints
		PolygonPointsLoop
		ThisPolygonPoint
		NextPolygonPoint
		X0
		X1
		Y0
		Y1
		XB
		YB
		SubPolygons
		SubPolygonToAdd
		)

        ; Importing global variables:
        ; the pitch along x where to break the polygon into subpolygons.
	    SubPolygonXPitch = GlobalSubPolygonXPitch

        ; Breaking the coordinates of the polygon into coordinates of sub-polygons
        ; Adding the first point of the polygon to the end (this way it is closed):
        PolygonPoints = append(PolygonPoints list(car(PolygonPoints)))

        ; Finiding minimum and maximum coordinate values.
        XMin = xCoord(car(PolygonPoints))
        XMax = xCoord(car(PolygonPoints))
        YMin = yCoord(car(PolygonPoints))
        YMax = yCoord(car(PolygonPoints))
        foreach( PolygonPoint PolygonPoints
            XMin = min(XMin xCoord(PolygonPoint))
            XMax = max(XMax xCoord(PolygonPoint))
            YMin = min(YMin yCoord(PolygonPoint))
            YMax = max(YMax yCoord(PolygonPoint))
        )

        ; Adding points which are on the boundaries.
        ; Scanning every pair of points in order to see if it crosses the boundary.
        ; initializing the temporary list. TempPolygonPoints will contain points exactly on multiples of
        ; SubPolygonXPitch.
        TempPolygonPoints = list(car(PolygonPoints))
        PolygonPointsLoop = PolygonPoints
        for(IndPolygonPoint 0 length(PolygonPoints)-1
            ThisPolygonPoint = car(PolygonPointsLoop)
            NextPolygonPoint = cadr(PolygonPointsLoop)
            if(NextPolygonPoint==nil then
                NextPolygonPoint=ThisPolygonPoint
            )

            X1 = xCoord(NextPolygonPoint)
            X0 = xCoord(ThisPolygonPoint)
            Y1 = yCoord(NextPolygonPoint)
            Y0 = yCoord(ThisPolygonPoint)

            if( floor(X0/SubPolygonXPitch) != floor(X1/SubPolygonXPitch)
            then
                ; then X0 is on one side and X1 is on the other side of a line located at x = N*SubPolygonXPitch
                if(X1>X0
                then
                    ; XB refers to boundary x coordinate
                    XB = SubPolygonXPitch * ( 1 + floor(X0/SubPolygonXPitch) )
                    while(XB < X1
                        YB = Y0 * (X1-XB)/(X1-X0) + Y1 * (XB-X0)/(X1-X0)
                        TempPolygonPoints = cons(list(XB YB) TempPolygonPoints)
                        XB = XB + SubPolygonXPitch
                    ) ; end while
                    TempPolygonPoints = cons(NextPolygonPoint TempPolygonPoints)
                else
                    XB = SubPolygonXPitch * floor(X0/SubPolygonXPitch)
                    while(XB > X1
                        YB = Y0 * (X1-XB)/(X1-X0) + Y1 * (XB-X0)/(X1-X0)
                        TempPolygonPoints = cons(list(XB YB) TempPolygonPoints)
                        XB = XB-SubPolygonXPitch
                    ) ; end while
                    TempPolygonPoints = cons(NextPolygonPoint TempPolygonPoints)
                ); end if(X1>X0
            else
                TempPolygonPoints = cons(NextPolygonPoint TempPolygonPoints)
            ) ; end if

            PolygonPointsLoop = cdr(PolygonPointsLoop)
        ) ; Now TempPolygonPoints contains all the points located at the sub-polygons boundaries.

        ; The old list "PolygonPoints" is updated to contain the coordinates located ON the boundary between
        ; subPolygons.
	    PolygonPoints = TempPolygonPoints

        ; Dividing the list of points in sublists.
	    SubPolygons = nil ; initialization
        for(IndSubPolygon floor(XMin/SubPolygonXPitch) floor(XMax/SubPolygonXPitch)
            SubPolygonToAdd = setof(PolygonPoint PolygonPoints
                                    IndSubPolygon*SubPolygonXPitch-0.5*GridSize <= xCoord(PolygonPoint) &&
                                    xCoord(PolygonPoint) <= (IndSubPolygon+1)*SubPolygonXPitch+0.5*GridSize)
                                    ; Bug: without 0.5*GridSize there are random rounding errors
            SubPolygons = cons( SubPolygonToAdd SubPolygons)
        )

        ; Returning result:
	    SubPolygons	; procedure returns this list
	) ; end of body of code (let)
) ; end of procedure definition





;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
; DeleteShapes
;
; This procedure deletes a list of shapes from the cellView
;
; Arguments
; ---------
;   Shapes :
;       The list of object IDs of the shapes to delete
;
; Returns
; -------
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

procedure( DeleteShapes(Shapes)
	let(
	    (
		    DeleteMe
		)

        ; Deleting the Shapes:
        foreach(DeleteMe Shapes
            if(dbIsId(DeleteMe)
            then
                dbDeleteObject(DeleteMe)
            )
        ) ; end foreach
	) ; end of body of code (let)
) ; end of procedure definition




;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
; CreateSubPolygons
;
; This procedure takes a list of coordinates of a polygon and creates a list of sub-polygons made of Manhattanized
; segments.
; This procedure is meant to be as similar as possible to dbCreatePolygons.
;
; Arguments
; ---------
;   CellView :
;       db address of the cell to flatten, for example CellView = pcCellView, or CellView = dbCreateParamInst( .... )
;   Lpp :
;       Layer on which shapes are to be created
;   CoordList :
;       List of points (arbitrarily long) that compose the polygons
;   ManhGridSize :
;       Grid size of Manhattanized grid
;   ManhattanTOrNil : Optional = GlobalManhattanTOrNil
;       True to Manhattanize the coordinate list
;
; Returns
; -------
;   DbObjects :
;       List of subpolygon shapes
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

procedure( CreateSubPolygons(CellView
                             Lpp
                             CoordList
                             ManhGridSize
                             @optional (ManhattanTOrNil GlobalManhattanTOrNil)
                             )
	let(
	    (
            GridSize
            NumVertices
            ManhattanCoordList
            SubPolygon
            SubPolygons
            DbTempObjects
            DbObject
            DbObjects
            Under
		)

        if( debug
        then
            printf("CreateSubPolygons\n")
        )

        ; Importing global variables:
	    GridSize = GlobalGridSize
	    NumVertices = GlobalNumVertices ; number of vertices used for boolean generation

        ; Manhattanize if required
        if( ManhattanTOrNil == t
        then
            ManhattanCoordList = Manh(CoordList ManhGridSize)
        else
            ManhattanCoordList = CoordList
        )

        ; Separating coordinate list in list of smaller coordinate lists:
        SubPolygons = CoordPrep(ManhattanCoordList ManhGridSize)
        ; Creating a subpolygon for coordinate list:
        DbTempObjects = nil
        foreach(SubPolygon SubPolygons
            DbTempObjects = cons(dbCreatePolygon(CellView Lpp SubPolygon) DbTempObjects)
        )

        ; Performing Over(Under()) by one grid-size for disconnecting disconnected shapes:
        Under = dbLayerSize(CellView Lpp DbTempObjects -GridSize NumVertices)
        DbObjects = dbLayerSize(CellView Lpp Under GridSize NumVertices)

        ; Deleting useless shapes:
        Flatten(CellView)
        DeleteShapes(DbTempObjects)
        Flatten(CellView)
        DeleteShapes(Under)
        Flatten(CellView)

        ; Removing "nil" entries.
        DbObjects = setof(DbObject DbObjects DbObject!= nil)
        DbObjects	; procedure returns this list
	) ; end of body of code (let)
) ; end of procedure




;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
; CreateRoughShapes
;
; This procedure takes all shapes on LppIn, makes them rougher (on the GlobalRoughGridSize) and sizes them by
; 2.0*GlobalRoughGridSize.
; Shapes are written on the same LppIn. Object IDs of the rough shapes are returned.
; It additionally makes 2x Over(O), then 2x Under(U), then Over(O).
; This is to eliminate the risk that through Manhattanization knotted paths are formed
;
; Arguments
; ---------
;   CellView :
;       db address of the cell to flatten, for example CellView = pcCellView, or CellView = dbCreateParamInst( .... )
;   LppIn :
;       Layer on which shapes are to be roughened
;
; Returns
; -------
;   RoughShapes :
;       Roughened shapes
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

procedure( CreateRoughShapes(CellView
                             LppIn
                             )
	let(
	    (
		GridSize
		RoughGridSize
		NumVertices
		ShapesIn
		OOShapes
		UUOOShape
		UUOOShapes
		OUUOOShape
		OUUOOShapes
		RoughShapes
		TempCoords
		)

        ; Importing global variables:
        RoughGridSize = GlobalRoughGridSize
        NumVertices = GlobalNumVertices ; number of vertices used for boolean generation

        ; Flattening
	    Flatten(CellView)

        ; Transforming shapes:
        ShapesIn = setof(Shape CellView~>shapes Shape~>lpp == LppIn)
        OOShapes = dbLayerSize(CellView LppIn ShapesIn 2.0*RoughGridSize NumVertices)
        UUOOShapes = dbLayerSize(CellView LppIn OOShapes -2.0*RoughGridSize NumVertices)
        OUUOOShapes = dbLayerSize(CellView LppIn UUOOShapes RoughGridSize NumVertices)

        ; Making the OUUOOShapes rougher on LppIn:
        RoughShapes = nil ; initialization
        ; Creating for each shape a rougher one on the same input Lpp (will be deleted later):
        foreach(OUUOOShape OUUOOShapes
            if(OUUOOShape~>objType == "polygon"
            then
                RoughShapes = append(CreateSubPolygons(CellView LppIn OUUOOShape~>points RoughGridSize) RoughShapes)
            else
                if(OUUOOShape~>objType == "rect"
                then
                    TempCoords = list(
                        list(
                            RoughGridSize * round(xCoord(car(OUUOOShape~>bBox))/RoughGridSize)
                            RoughGridSize * round(yCoord(car(OUUOOShape~>bBox))/RoughGridSize)
                        )
                        list(
                            RoughGridSize * round(xCoord(cadr(OUUOOShape~>bBox))/RoughGridSize)
                            RoughGridSize * round(yCoord(cadr(OUUOOShape~>bBox))/RoughGridSize)
                        )
                    )

                    RoughShapes = append( list(dbCreateRect(CellView LppIn TempCoords)) RoughShapes)
                else
                    fprintf(woport "Error in 0ProcedureDataPrep. Shape is nor polygon nor rectangle. \n")
                ) ; end if
            ) ; end if.
        ) ; end foreach.
        ; Deleting useless shapes:
        DeleteShapes( OUUOOShapes )
        DeleteShapes( UUOOShapes )
        DeleteShapes( OOShapes )

        ; Returning result:
        RoughShapes	; procedure returns this value
	) ; end of body of code (let)
) ; end of procedure definition



;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
; LayerExtend
;
; ; This procedure extends the layer-purpose-pair LppToExtend over the edge of LppReference by the amount ExtendAmount.
; If an edge of LppToExtend crosses LppReference, this edge remains untouched.
; Added shapes are copied for layer ("addedphot" "dataprep") for checking.
;
; Arguments
; ---------
;   CellView :
;       db address of the cell to flatten, for example CellView = pcCellView, or CellView = dbCreateParamInst( .... )
;   LppToExtend :
;       Layer on which shapes are extended
;   LppReference :
;       Reference layer over which shapes are extended
;   ExtendAmount :
;       Amount by which LppToExtend shapes are extended over LppReference
;
; Returns
; -------
;   CellView :
;       db address of cell post layer extension
;
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

procedure( LayerExtend(CellView
                       LppToExtend
                       LppReference
                       ExtendAmount
                       )
	let(
	    (
            GridSize
            NumVertices
            Shape
            ShapesToExtend
            ShapesReference
            ShapesExtended
            ShapeExtra
            SizeAmount
		)

        ; Import global variables:
        GridSize = GlobalGridSize
        NumVertices = GlobalNumVertices

        ; Round extend amount to the grid size:
        ExtendAmount = GridSize * ceiling(ExtendAmount/GridSize)

        ; Flattening
	    Flatten(CellView)

        ; Finding the shapes on LppToExtend:
	    ShapesToExtend = setof(Shape CellView~>shapes Shape~>lpp == LppToExtend)

        ; Finding the shapes on LppReference:
	    ShapesReference = setof(Shape CellView~>shapes Shape~>lpp == LppReference)

        ; Sizing the shapes on LppReference for later use:
	    SizedShapesReference = dbLayerSize(CellView LppReference ShapesReference ExtendAmount NumVertices)

        ; Extending shapes (making Over):
	    ShapesExtended = dbLayerSize(CellView LppToExtend ShapesToExtend ExtendAmount NumVertices)

        ; Subtracting the result from LppReference
	    ShapeExtra = dbLayerAndNot(CellView LppToExtend ShapesExtended ShapesReference NumVertices)

        ; Intersect ShapeExtra with SizedShapesReference:
	    ShapesToAdd = dbLayerAnd(CellView LppToExtend ShapeExtra SizedShapesReference NumVertices)

        ; Deleting shapes:
        Flatten(CellView)
        DeleteShapes( ShapesExtended )
        DeleteShapes( ShapeExtra )
        DeleteShapes( SizedShapesReference )

        ; Cleaning away the small bumps with OverOfUnder:
        SizeAmount = max(GridSize * ceiling(0.5*ExtendAmount/GridSize+1.1) 0.0)
        ; 1.1 is inserted to make sure that shapes disappear (independently from rounding errors).
        LayerOverOfUnder(CellView LppToExtend LppToExtend SizeAmount)

        ; Return result:
        CellView	; procedure returns this value
	) ; end of body of code (let)
) ; end of procedure definition






;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
; LayerOverOfUnder
;
; This procedure makes an under operation, then an over operation for eliminating DRC-critical features
; such as acute angles, on the specified layer-purpose-pair LppIn and writes the result on LppOut.
; All input shapes are deleted.
; The name "OverOfUnder" was chosen for eliminating ambiguity of which operation is performed first. Indeed,
; Calibre understands by "overunder" the opposite operation (where over is performed first). Here however the general
; convention is to read things from right to left.
; The procedure takes a database object ID, for example a pCell or an instantiation, FLATTENS it, and performs
; on the specified layer-purpose-pair Lpp the operations "over" (or "size" by a positive amount)
; and "under" (or "size" by the same but negative amount). The difference
; is added to the original layer and to the layer ("addedphot" "dataprep") for checking.
; The difference is removed from the original layer and written to ("removedphot" "dataprep").
; Intermediate objects are cleared. It is returned the same objectID as the input.
;
; Arguments
; ---------
;   CellView :
;       db address of the cell on which to perform OverOfUnder
;   LppOut :
;       Layer on which OverOfUnder shapes are drawn
;   LppIn :
;       Layer on whose shapes OverOfUnder is performed
;
; Returns
; -------
;   ReturnShapes :
;       The newly generated shapes
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

procedure(LayerOverOfUnder(CellView
                           LppOut
                           LppIn
                           SizeAmount
                           )
	let(
	    (
            GridSize
            NumVertices
            Shape
            Shapes
            Under
            OverOfUnder
            Excess
            Defect
            DeleteMe
            ReturnShapes
		)

        ; Importing global variables:
        GridSize = GlobalGridSize
        NumVertices = GlobalNumVertices ; number of vertices used for boolean generation

        ; Rounding to the grid
        SizeAmount = GridSize*ceiling(SizeAmount/GridSize)

        ; Flattening
        Flatten(CellView)

        ; Finding the shapes with the correct layer purpose pair (LppIn):
        Shapes = setof(Shape CellView~>shapes Shape~>lpp == LppIn)

        ; Making Under then Over:
        Under = dbLayerSize(CellView LppOut Shapes -SizeAmount NumVertices)
        OverOfUnder = dbLayerSize(CellView LppOut Under SizeAmount NumVertices)
        ReturnShapes = OverOfUnder

        ; This must be a BUG of SKILL: you need to run dbLayerAndNot TWICE to get all the shapes out:
        dbLayerAndNot(CellView list("addedphot" 	"dataprep") OverOfUnder Shapes NumVertices)
        dbLayerAndNot(CellView list("removedphot" 	"dataprep") Shapes OverOfUnder NumVertices)

        ; Deleting shapes
        Flatten(CellView)
        DeleteShapes( Shapes )
        Flatten(CellView)
        DeleteShapes( Under )
        Flatten(CellView)

        ; Returning result
        ReturnShapes
	) ; end of body of code (let)
) ; end of procedure definition




;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
; LayerUnderOfOver
;
; This procedure makes an over operation, then an under operation for eliminating DRC-critical features
; such as acute angles, on the specified layer-purpose-pair LppIn and writes the result on LppOut.
; All input shapes are deleted.
; The name "UnderOfOver" was chosen for eliminating ambiguity of which operation is performed first. Indeed,
; Calibre understands by "underover" the opposite operation (where under is performed first). Here however the general
; convention is to read things from right to left.
; The procedure takes a database object ID, for example a pCell or an instantiation, FLATTENS it, and performes
; on the specified layer-purpose-pair Lpp the operations "over" (or "size" by a positive amount)
; and "under" (or "size" by the same but negative amount). The difference
; is added to the original layer and to the layer ("addedphot" "dataprep") for checking.
; The difference is removed from the original layer and written to ("removedphot" "dataprep").
; Intermediate objects are cleared. It is returned the same objectID as the input.
;
; Arguments
; ---------
;   CellView :
;       db address of the cell on which to perform OverOfUnder
;   LppOut :
;       Layer on which OverOfUnder shapes are drawn
;   LppIn :
;       Layer on whose shapes OverOfUnder is performed
;
; Returns
; -------
;   ReturnShapes :
;       The newly generated shapes
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

procedure( LayerUnderOfOver(CellView
                            LppOut
                            LppIn
                            SizeAmount
                            )
	let(
	    (
            GridSize
            NumVertices
            Shape
            Shapes
            Over
            UnderOfOver
            DeleteMe
            ReturnShapes
		)

        ; Importing global variables:
        GridSize = GlobalGridSize
        NumVertices = GlobalNumVertices ; number of vertices used for boolean generation

        ; Rounding to the grid
        SizeAmount = GridSize * ceiling(SizeAmount/GridSize)

        ; Flattening
        Flatten(CellView)

        ; Finding the shapes with the correct layer purpose pair (LppIn):
        Shapes = setof(Shape CellView~>shapes Shape~>lpp == LppIn)

        ; Making Over then Under:
        Over = dbLayerSize(CellView LppOut Shapes SizeAmount NumVertices)
        UnderOfOver = dbLayerSize(CellView LppOut Over -SizeAmount NumVertices)
        ReturnShapes=UnderOfOver

        ; This must be a BUG of SKILL: you need to run dbLayerAndNot TWICE to get all the shapes out:
        dbLayerAndNot(CellView list("addedphot" 	"dataprep") UnderOfOver Shapes NumVertices)
        dbLayerAndNot(CellView list("removedphot" 	"dataprep") Shapes UnderOfOver NumVertices)

        ; Deleting shapes:
        Flatten(CellView)
        DeleteShapes( Shapes )
        Flatten(CellView)
        DeleteShapes( Over )
        Flatten(CellView)

        ; Returning result:
        ReturnShapes
	) ;end of body of code (let)
) ; end of procedure definition





;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
; DataPrep
;
; This procedure takes a database object ID, for example a pCell, FLATTENS it, and performs the instructions defined by
; the global variable DataPrepGroups.
; Layer-purpose-pairs specified in the list NotToExtendOrOverUnderOrUnderOverLpps will not undergo Extension,
; OverOfUnder and UnderOfOver operation.
;
; Arguments
; ---------
;   CellView :
;       db address of the cell to flatten, for example CellView = pcCellView, or CellView = dbCreateParamInst( .... )
;   NotToExtendOrOverUnderOrUnderOverLpps :
;       list of layer-purpose-pairs which should NOT be drc-cleaned.
;       These layers will not undergo Extend, OverOfUnder, or UnderOfOver operations.
;       Example: NotToExtendOrOverUnderOrUnderOverLpps = nil, or list(list("rx" "drawing"))
;   DebugText : Optional = t
;       True to print debug information
;
; Returns
; -------
;   CellView :
;       db address of the dataprep-ed cell
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

procedure( DataPrep(CellView
                    NotToExtendOrOverUnderOrUnderOverLpps
                    @optional (DebugText t)
                    )
	let(
	    (
            GridSize
            RoughGridSize
            NumVertices
            DataPrepGroup
            DataPrepGroups
            ShapesToSubtract
            LppIn	LppsIn
            LppOut
            Operation
            SizeAmount
            OverOfUnderSizeAmount
            UnderOfOverSizeAmount
            RoughShapes
            ShapeOut
            ShapesOut
            Shape
            Shapes
            ShapesIn
            Info
            Infos
            NeedNewRoughShapes
		)
		printf("Running DataPrep\n")

        ; Importing global variables:
        GridSize = GlobalGridSize
        RoughGridSize = GlobalRoughGridSize
        NumVertices = GlobalNumVertices
        DataPrepGroups = GlobalDataPrepGroups

        ; Flatten the cell
        Flatten(CellView)

        ; Sweeping all parameters, first groups, then LppsIn, then Infos = LppOut, Operation, SizeAmount
        foreach(DataPrepGroup DataPrepGroups
            LppsIn = nth(0 DataPrepGroup)
            if( DebugText
            then
                printf("New DataPrepGroup \n")
            )
            foreach(LppIn LppsIn
                Infos = nth(1 DataPrepGroup)
                ShapesIn = setof(Shape CellView~>shapes Shape~>lpp == LppIn)
                NeedNewRoughShapes = t ; initialization
                RoughShapes = nil ; initialization
                foreach(Info Infos
                    LppOut = nth(0 Info)
                    Operation = nth(1 Info)
                    ; for "Ouo" nth(2 Info) is set to nil, so this is skipped.
                    if(nth(2 Info) SizeAmount = GridSize*round(nth(2 Info)/GridSize) )

                    if( Operation == "Rad"
                    then
                        if(NeedNewRoughShapes == t
                        then
                            ; rough shapes are written on LppIn and sized by 2.0*GlobalRoughGridSize.
                            RoughShapes = CreateRoughShapes(CellView LppIn)
                            NeedNewRoughShapes = nil
                        ) ; end if.
                        dbLayerSize(CellView
                                    LppOut
                                    RoughShapes
                                    max(SizeAmount - 2.0*GlobalRoughGridSize 0.0)
                                    NumVertices
                                    )
                        if(and(DebugText == t length(RoughShapes) > 0)
                            fprintf(woport "%L --> %L  %L rough shapes added. \n"
                                    LppIn,
                                    LppOut,
                                    list(length(RoughShapes))
                            )
                        ) ; end of if.
                    ) ; end if.

                    if( Operation == "Add"
                    then
                        dbLayerSize(CellView LppOut ShapesIn SizeAmount NumVertices)
                        if(and(DebugText == t length(ShapesIn) > 0)
                            fprintf(woport "%L --> %L  %L shapes added. \n"
                                    LppIn,
                                    LppOut,
                                    list(length(ShapesIn))
                            )
                        ) ; end of if.
                    ) ; end if.

                    if( Operation == "Sub"
                    then
                        ShapesOut = setof( ShapeOut CellView~>shapes ShapeOut~>lpp == LppOut)
                        ShapesToSubtract = dbLayerSize(CellView LppOut ShapesIn SizeAmount NumVertices)
                        dbLayerAndNot(CellView LppOut ShapesOut ShapesToSubtract NumVertices)
                        if(and(DebugText == t length(ShapesToSubtract) > 0)
                            fprintf(woport "%L --> %L  %L shapes subtracted. \n"
                                    LppIn,
                                    LppOut,
                                    list(length(ShapesToSubtract))
                            )
                        ) ; end of if.
                        ; giving warning if there is nothing to subtract from:
                        if( ShapesOut == nil
                            fprintf(woport "Warning in 0ProcedureDataPrep. There is nothing to substract %L from. \n" LppOut)
                        ) ; end if.
                        DeleteShapes(ShapesToSubtract)
                        DeleteShapes(ShapesOut)
                    ) ; end if.

                    if( Operation == "Ext"
                    then
                        if( not(member(LppOut NotToExtendOrOverUnderOrUnderOverLpps)!= nil)
                        then
                            if(DebugText == t
                                fprintf(woport "Extending %L over %L by %L . \n" LppIn LppOut list(SizeAmount))
                            ) ; end of if.
                            LayerExtend(CellView LppIn LppOut SizeAmount)
                        else
                            if(DebugText == t
                                fprintf(woport "Extension skipped on %L over %L by %L . \n"
                                        LppIn
                                        LppOut
                                        list(SizeAmount)
                                )
                            ) ; end of if.
                        ) ; end if.
                    ) ; end if.

                    if( Operation == "ouo"
                    then
                        printf("Performing OUO on \n")
                        ; Perform Over Under Under Over only if LppOut is not in the list
                        ; NotToExtendOrOverUnderOrUnderOverLpps:
                        if( not(member(LppIn NotToExtendOrOverUnderOrUnderOverLpps)!= nil)
                        then
                            if(and(DebugText == t length(ShapesIn) > 0)
                                fprintf(woport "Performing Over of Under of Under of Over on %L. \n"  LppIn )
                            )  ; end of if.
                            ; giving error if necessary:
                            if( GlobalGR("MinWidth" car(LppIn) nil) == nil
                                printf( "Error in 0ProcedureDataPrep.il: MinWidth for %L is missing in 0GlobalVariables.il.  \n" LppIn)
                            ) ; This will make pCell not usable.
                            if( GlobalGR("MinSpace" car(LppIn) nil) == nil
                                printf( "Error in 0ProcedureDataPrep.il: MinSpace for %L is missing in 0GlobalVariables.il.  \n" LppIn)
                            ) ; This will make pCell not usable.

                            ; Getting values:
                            ;; UnderOfOverSizeAmount = GridSize * ceiling(0.5*GlobalGR("MinSpace" car(LppIn) nil)/GridSize) ; Luca, 2015_03_04
                            ;; OverOfUnderSizeAmount = GridSize * ceiling(0.5*GlobalGR("MinWidth" car(LppIn) nil)/GridSize)	; Luca, 2015_03_04
                            ;; UnderOfOverSizeAmount = 0.5*GlobalGR("MinSpace" car(LppIn) nil)+0.5*GridSize 	; Luca, 2015_03_04, this will preserve shapes on exact critical dimension
                            ;; OverOfUnderSizeAmount = 0.5*GlobalGR("MinWidth" car(LppIn) nil)-0.5*GridSize 	; Luca, 2015_03_04, this will preserve shapes on exact critical dimension
                            ;; UnderOfOverSizeAmount = 0.5*GlobalGR("MinSpace" car(LppIn) nil)-0.3*GridSize 	; Luca, 2015_03_07, correcting sign
                            ;; OverOfUnderSizeAmount = 0.5*GlobalGR("MinWidth" car(LppIn) nil)-0.3*GridSize 	; Luca, 2015_03_07, diminishing value (after gridsize changed to 0.5 in techfile)
                            UnderOfOverSizeAmount = GridSize * ceiling(0.5*GlobalGR("MinSpace" car(LppIn) nil)/GridSize) ; Luca, 2015_03_14, changing back to LTP1 status after gridSize returned to original 1nm (from 0.005) in tech.db
                            OverOfUnderSizeAmount = GridSize * ceiling(0.5*GlobalGR("MinWidth" car(LppIn) nil)/GridSize) ; Luca, 2015_03_14, changing back to LTP1 status after gridSize returned to original 1nm (from 0.005) in tech.db

                            ; Making Under of Over:
                            LayerUnderOfOver(CellView LppIn LppIn UnderOfOverSizeAmount)

                            ; Making Over of Under:
                            LayerOverOfUnder(CellView LppIn LppIn OverOfUnderSizeAmount)
                            ;LayerOverOfUnder(CellView LppOut LppOut OverOfUnderSizeAmount)
                        ) ; end if.
                    ) ; end if.

                    if( Operation == "Del"
                    then
                        DeleteShapes(ShapesIn)
                    ) ; end if.

                ) ; end foreach Info

                ; Deleting potential RoughShapes:
                DeleteShapes(RoughShapes)

            ) ; end foreach LppIn
        ) ; end foreach DataPrepGroup

        ; Returning result:
        CellView	; procedure returns this value
    ) ;end of body of code (let)
) ; end of procedure definition





;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
; DataPrepWrapper
;
; This procedure performs DataPrep on a cell.
; It takes a lib name and cell name, and creates a new dataprep-ed cell in the
; same library and with cell_name_DataPrep.
;
; Arguments
; ---------
;   lib_name :
;       Name of library in which cell to dataprep resides
;   cell_name :
;       Name of cell to dataprep
;   debug : Optional = nil
;       t to print debug information
;
; Returns
; -------
;   --  :
;       Throws error if DataPrep fails
;
; Outputs
; -------
;   lib_nam__cell_name_DataPrep :
;       Output cellview that is the dataprep-ed version of the original cell view
;       Original cellview is not modified.
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

procedure( DataPrepWrapper(lib_name
                           cell_name
                           @optional (debug nil)
                           )
    let(
        (
            cv
            dp_cv
        )

        ; Try to get the dB object of the cellview
        unless( cv = dbOpenCellViewByType( lib_name cell_name "layout" "maskLayout" "r")
            error("DataPrepWrapper: Cannot open cellView %s__%s (layout)." lib_name cell_name)
        )

        ; Try to get the dB object of the new dataprep-ed cellview
        unless( dp_cv = dbOpenCellViewByType( lib_name strcat(cell_name "_DataPrep") "layout" "maskLayout" "w")
            error("DataPrepWrapper: Cannot create new cellView %s__%s (layout)." lib_name strcat(cell_name "_DataPrep"))
        )

        inst = dbCreateInst(dp_cv cv "DataPrep" '(0 0) "R0")
        dbClose(cv)

        printf("Just before dataprep\n")
        DataPrep(dp_cv nil debug)

        dbSave(dp_cv)
        dbClose(dp_cv)

    ) ; end let
) ; end procedure



procedure( ManhCell(lib_name
                    cell_name
                    @optional (debug nil)
                    )
    let(
        (
            cv
            dp_cv
            new_shapes
            lpp
            GlobalManhTOrNil
            TempCoords
        )
        GlobalManhattanTOrNil = 't  ; # TODO
        if( debug
        then
            printf("ManhCell\n")
        )

        ; debug = 't  ; # TODO
        ; Try to get the dB object of the cellview
        unless( cv = dbOpenCellViewByType( lib_name cell_name "layout" "maskLayout" "r")
            error("DataPrepWrapper: Cannot open cellView %s__%s (layout)." lib_name cell_name)
        )

        ; Try to get the dB object of the new dataprep-ed cellview
        unless( dp_cv = dbOpenCellViewByType( lib_name strcat(cell_name "_Manh") "layout" "maskLayout" "w")
            error("DataPrepWrapper: Cannot create new cellView %s__%s (layout)." lib_name strcat(cell_name "_Manh"))
        )

        inst = dbCreateInst(dp_cv cv "DataPrep" '(0 0) "R0")

;        ShapesIn = setof(Shape CellView~>shapes Shape~>lpp == LppIn)

        Flatten(dp_cv)

        new_shapes = nil
        foreach(shape dp_cv~>shapes
            printf("in foreach \n")
            printf(shape~>objType)
            lpp = shape~>lpp
            if(shape~>objType == "rect"
            then
                printf("rect path\n")
                TempCoords = list(
                        list(
                            xCoord(car(shape~>bBox))
                             yCoord(car(shape~>bBox))
                        )
                        list(
                            xCoord(cadr(shape~>bBox))
                            yCoord(cadr(shape~>bBox))
                        )
                    )
                new_shapes = append( list(dbCreateRect(dp_cv lpp TempCoords)) new_shapes)
                DeleteShapes(list(shape))
            else
                if( shape~>objType == "polygon"
                then
                    printf("polygon path\n")
                    new_shapes = append(CreateSubPolygons(dp_cv lpp shape~>points GlobalGridSize) new_shapes) ; # TODO
                DeleteShapes(list(shape))
                )
            )
            ; Manh(shape GlobalManhGridSize)
;            DeleteShapes(shape)
        )
        dbSave(dp_cv)
        dbClose(dp_cv)
        dbClose(cv)


    ) ; end let
) ; end procedure


printf("\n\n\nDefined skill dataprep functions successfully!\n\n\n")